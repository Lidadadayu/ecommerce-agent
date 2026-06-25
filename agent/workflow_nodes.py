from __future__ import annotations

from typing import Any, cast

from agent.legacy_agent import (
    _basic_chat_fallback,
    _build_route,
    _friendly_error_reply,
    _format_context_notice,
    _maybe_set_pending_action,
)
from agent.rag_policy_helper import enrich_template_answer_with_rag
from agent.rule_agent import generate_answer
from agent.slot_filling import build_effective_tool_arguments
from agent.state import build_initial_state
from agent.task_planner import choose_route_for_task, plan_user_task
from agent.task_state_machine import update_task_after_tool
from agent.tool_result_handler import handle_tool_result
from agent.graph_state import EcommerceGraphState
from agent.human_review import apply_human_review_to_tool_result, format_human_review_notice
from agent.human_review_queue import (
    create_human_review_task,
    format_human_review_task_notice,
)
from agent.llm_client import chat_with_llm, rewrite_tool_answer
from agent.memory import SessionMemory
from agent.next_best_action import append_next_best_actions, recommend_next_actions
from tools.tool_registry import execute_tool


def _append_and_export_memory(
    *,
    memory_obj: SessionMemory,
    state: EcommerceGraphState,
    final_answer: str,
) -> dict[str, Any]:
    route = state.get("route") or {}

    memory_obj.append_turn(
        state.get("user_query", ""),
        final_answer,
        route.get("intent"),
        route.get("tool_name"),
    )

    agent_state = state.get("agent_state") or {}
    agent_state["memory"] = memory_obj.to_dict()
    agent_state["final_answer"] = final_answer

    return agent_state


def _extract_evidence_ids_from_memory(memory_obj: SessionMemory) -> list[str]:
    context = getattr(memory_obj, "current_business_context", {}) or {}
    evidence_ids = context.get("evidence_ids") or []
    evidence_files = context.get("evidence_files") or []

    ids: list[str] = []

    if isinstance(evidence_ids, list):
        ids.extend(str(x) for x in evidence_ids if x)

    if isinstance(evidence_files, list):
        for item in evidence_files:
            if isinstance(item, dict) and item.get("evidence_id"):
                ids.append(str(item["evidence_id"]))

    # 去重且保序。
    unique: list[str] = []
    for item in ids:
        if item not in unique:
            unique.append(item)
    return unique[:10]


def initialize_node(state: EcommerceGraphState) -> dict[str, Any]:
    input_memory = state.get("input_memory")
    memory_obj = SessionMemory.from_dict(input_memory) if isinstance(input_memory, dict) else SessionMemory()
    memory_obj.update_from_user_query(state.get("user_query", ""))

    return {
        "memory_obj": memory_obj,
        "input_memory": input_memory,
    }


def routing_node(state: EcommerceGraphState) -> dict[str, Any]:
    user_query = state.get("user_query", "")
    memory_obj = cast(SessionMemory, state["memory_obj"])

    task_plan = plan_user_task(user_query, memory_obj)
    route, used_memory, domain = _build_route(user_query, memory_obj)
    route = choose_route_for_task(route, user_query, memory_obj)
    agent_state = cast(dict[str, Any], build_initial_state(user_query, route, used_memory=used_memory))
    agent_state["domain"] = domain
    agent_state["route"] = route
    agent_state["intent"] = route.get("intent")
    agent_state["tool_name"] = route.get("tool_name")
    agent_state["task_plan"] = task_plan.get("task_state")

    return {
        "route": route,
        "used_memory": used_memory,
        "domain": domain,
        "agent_state": agent_state,
        "task_plan": task_plan,
    }


def fixed_domain_response_node(state: EcommerceGraphState) -> dict[str, Any]:
    memory_obj = cast(SessionMemory, state["memory_obj"])
    domain = state.get("domain") or {}
    route = state.get("route") or {}
    agent_state = state.get("agent_state") or {}

    if not domain.get("allowed", True):
        mode = "domain_rejected"
        final_answer = domain.get("reply") or "抱歉，这个问题不在当前电商售后与运营 Agent 的处理范围内。"
    else:
        mode = f"{domain.get('category', 'domain')}_reply"
        final_answer = domain.get("reply") or "你好，我是电商售后与运营 Agent 助手。"

    agent_state["mode"] = mode
    agent_state["used_llm"] = False
    agent_state["intent"] = route.get("intent")
    agent_state["tool_name"] = route.get("tool_name")

    agent_state = _append_and_export_memory(
        memory_obj=memory_obj,
        state=state,
        final_answer=final_answer,
    )

    return {
        "agent_state": agent_state,
    }


def general_chat_response_node(state: EcommerceGraphState) -> dict[str, Any]:
    memory_obj = cast(SessionMemory, state["memory_obj"])
    agent_state = state.get("agent_state") or {}
    user_query = state.get("user_query", "")

    llm_result = chat_with_llm(
        user_query,
        fallback_content=_basic_chat_fallback(user_query),
    )

    final_answer = llm_result.get("content") or _basic_chat_fallback(user_query)

    agent_state["used_llm"] = True
    agent_state["mode"] = "general_chat"
    agent_state["llm_error"] = llm_result.get("error")

    agent_state = _append_and_export_memory(
        memory_obj=memory_obj,
        state=state,
        final_answer=final_answer,
    )

    return {
        "agent_state": agent_state,
    }


def slot_missing_response_node(state: EcommerceGraphState) -> dict[str, Any]:
    memory_obj = cast(SessionMemory, state["memory_obj"])
    route = state.get("route") or {}
    agent_state = state.get("agent_state") or {}
    user_query = state.get("user_query", "")

    _maybe_set_pending_action(route, memory_obj)

    if route.get("intent") in {"aftersale_check", "ticket_create"}:
        try:
            from agent.followup_strategy import build_context_aware_followup

            missing_slots = []
            error = route.get("error") or ""
            for slot, words in {
                "order_id": ["订单号"],
                "reason": ["原因"],
                "package_status": ["拆封", "使用"],
                "product_id": ["商品 ID", "商品名称"],
                "ticket_type": ["售后类型"],
            }.items():
                if any(word in error for word in words):
                    missing_slots.append(slot)
            final_answer = build_context_aware_followup(
                missing_slots=missing_slots,
                arguments=route.get("arguments") or {},
                memory=memory_obj,
                intent=route.get("intent"),
            )
        except Exception:
            final_answer = route.get("error") or "还需要补充售后相关信息。"
        agent_state["used_llm"] = False
        agent_state["mode"] = "aftersale_slot_missing"
    else:
        final_answer = _friendly_error_reply(user_query, route, memory_obj)
        agent_state["used_llm"] = True
        agent_state["mode"] = "slot_missing"

    agent_state = _append_and_export_memory(
        memory_obj=memory_obj,
        state=state,
        final_answer=final_answer,
    )

    return {
        "agent_state": agent_state,
    }


def tool_call_node(state: EcommerceGraphState) -> dict[str, Any]:
    route = state.get("route") or {}
    agent_state = state.get("agent_state") or {}
    memory_obj = cast(SessionMemory, state["memory_obj"])

    effective_arguments = build_effective_tool_arguments(
        route.get("intent"),
        route.get("arguments") or {},
    )

    if route.get("intent") == "ticket_create" and "evidence_ids" not in effective_arguments:
        evidence_ids = _extract_evidence_ids_from_memory(memory_obj)
        if evidence_ids:
            effective_arguments["evidence_ids"] = evidence_ids

    tool_result = execute_tool(route.get("tool_name"), effective_arguments)
    update_task_after_tool(
        memory_obj,
        intent=route.get("intent"),
        tool_name=route.get("tool_name"),
        arguments=effective_arguments,
        tool_result=tool_result,
    )

    agent_state["arguments"] = effective_arguments
    agent_state["tool_result"] = tool_result

    return {
        "effective_arguments": effective_arguments,
        "tool_result": tool_result,
        "agent_state": agent_state,
    }


def tool_result_handler_node(state: EcommerceGraphState) -> dict[str, Any]:
    memory_obj = cast(SessionMemory, state["memory_obj"])
    route = state.get("route") or {}

    handled = handle_tool_result(
        intent=route.get("intent"),
        tool_name=route.get("tool_name"),
        arguments=state.get("effective_arguments") or {},
        tool_result=state.get("tool_result") or {},
        memory=memory_obj,
    )

    return {
        "handled_result": handled,
    }


def handled_tool_response_node(state: EcommerceGraphState) -> dict[str, Any]:
    memory_obj = cast(SessionMemory, state["memory_obj"])
    route = state.get("route") or {}
    agent_state = state.get("agent_state") or {}
    handled = state.get("handled_result") or {}

    final_answer = handled.get("final_answer") or "当前工具结果需要进一步确认。"
    actions = recommend_next_actions(
        intent=route.get("intent"),
        arguments=state.get("effective_arguments") or {},
        tool_result=state.get("tool_result") or {},
        memory=memory_obj,
    )
    final_answer = append_next_best_actions(final_answer, actions)

    agent_state["used_llm"] = False
    agent_state["mode"] = handled.get("mode", "tool_result_handled")
    agent_state["final_answer"] = final_answer

    memory_obj.update_after_tool_call(
        route.get("intent"),
        route.get("tool_name"),
        state.get("effective_arguments") or {},
        state.get("tool_result") or {},
    )

    agent_state = _append_and_export_memory(
        memory_obj=memory_obj,
        state=state,
        final_answer=final_answer,
    )

    return {
        "agent_state": agent_state,
    }


def human_review_node(state: EcommerceGraphState) -> dict[str, Any]:
    memory_obj = cast(SessionMemory, state["memory_obj"])
    route = state.get("route") or {}
    agent_state = state.get("agent_state") or {}

    force_create = bool((route.get("arguments") or {}).get("force_create", False))

    tool_result, human_review = apply_human_review_to_tool_result(
        intent=route.get("intent"),
        tool_result=state.get("tool_result") or {},
        force_create=force_create,
    )

    memory_obj.update_after_tool_call(
        route.get("intent"),
        route.get("tool_name"),
        state.get("effective_arguments") or {},
        tool_result,
    )

    template_answer = generate_answer(route.get("intent"), tool_result)
    template_answer = enrich_template_answer_with_rag(
        user_query=state.get("user_query", ""),
        intent=route.get("intent"),
        template_answer=template_answer,
        tool_result=tool_result,
    )

    review_task = create_human_review_task(
        user_query=state.get("user_query", ""),
        intent=route.get("intent"),
        tool_name=route.get("tool_name"),
        arguments=state.get("effective_arguments") or {},
        tool_result=tool_result,
        human_review=human_review,
        memory=memory_obj.to_dict(),
        final_answer=template_answer,
    )

    template_answer = (
        f"{template_answer}"
        f"{_format_context_notice(bool(state.get('used_memory')), memory_obj)}"
        f"{format_human_review_notice(human_review)}"
        f"{format_human_review_task_notice(review_task)}"
    )
    template_answer = append_next_best_actions(
        template_answer,
        recommend_next_actions(
            intent=route.get("intent"),
            arguments=state.get("effective_arguments") or {},
            tool_result=tool_result,
            memory=memory_obj,
        ),
    )

    memory_obj.clear_pending_action()

    agent_state["tool_result"] = tool_result
    agent_state["template_answer"] = template_answer
    agent_state["human_review"] = human_review
    agent_state["human_review_task"] = review_task

    return {
        "tool_result": tool_result,
        "human_review": human_review,
        "human_review_task": review_task,
        "template_answer": template_answer,
        "agent_state": agent_state,
    }


def response_rewrite_node(state: EcommerceGraphState) -> dict[str, Any]:
    memory_obj = cast(SessionMemory, state["memory_obj"])
    route = state.get("route") or {}
    agent_state = state.get("agent_state") or {}

    llm_result = rewrite_tool_answer(
        user_query=state.get("user_query", ""),
        intent=route.get("intent"),
        tool_name=route.get("tool_name"),
        arguments=state.get("effective_arguments") or {},
        tool_result=state.get("tool_result") or {},
        template_answer=state.get("template_answer") or "",
        human_review=state.get("human_review"),
    )

    final_answer = llm_result.get("content") or state.get("template_answer") or "请求已处理。"
    final_answer = append_next_best_actions(
        final_answer,
        recommend_next_actions(
            intent=route.get("intent"),
            arguments=state.get("effective_arguments") or {},
            tool_result=state.get("tool_result") or {},
            memory=memory_obj,
        ),
    )

    agent_state["used_llm"] = True
    agent_state["mode"] = "langgraph_multi_agent_orchestration"
    agent_state["llm_error"] = llm_result.get("error")
    agent_state["final_answer"] = final_answer

    agent_state = _append_and_export_memory(
        memory_obj=memory_obj,
        state=state,
        final_answer=final_answer,
    )

    return {
        "agent_state": agent_state,
    }
