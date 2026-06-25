from __future__ import annotations
from agent.rag_policy_helper import enrich_template_answer_with_rag
from typing import Any, cast

from agent.llm_router import route_with_llm
from agent.rule_agent import generate_answer
from agent.rule_router import extract_ticket_type, is_check_question, is_create_ticket_request, route_user_query
from agent.slot_filling import (
    build_aftersale_slot_reply,
    build_effective_tool_arguments,
    merge_aftersale_slots,
    missing_aftersale_slots,
)
from agent.state import build_initial_state
from agent.task_planner import choose_route_for_task, plan_user_task
from agent.task_state_machine import get_task_state, update_task_after_tool
from agent.tool_result_handler import handle_tool_result
from agent.patterns import is_only_order_id
from agent.domain_guard import build_capability_reply, check_domain_scope
from agent.human_review import apply_human_review_to_tool_result, format_human_review_notice
from agent.llm_client import chat_with_llm, rewrite_tool_answer
from agent.memory import SessionMemory
from agent.next_best_action import append_next_best_actions, recommend_next_actions
from tools.tool_registry import execute_tool


INTENT_TO_TOOL = {
    "order_query": "order_query",
    "recent_orders": "recent_orders",
    "order_cancel": "order_cancel",
    "shipment_urge": "shipment_urge",
    "refund_progress": "refund_progress",
    "operation_metrics": "operation_metrics",
    "logistics_query": "logistics_query",
    "ticket_query": "ticket_query",
    "purchase_history": "purchase_history",
    "aftersale_check": "aftersale_check",
    "ticket_create": "ticket_create",
    "product_detail": "product_detail",
    "product_search": "product_search",
    "policy_query": "policy_query",
    "robot_vacuum_search": "robot_vacuum_search",
    "robot_vacuum_detail": "robot_vacuum_detail",
    "robot_vacuum_compare": "robot_vacuum_compare",
    "robot_vacuum_knowledge_query": "robot_vacuum_knowledge_query",
    "robot_vacuum_diagnosis": "robot_vacuum_diagnosis",
    "screenshot_order_review": "screenshot_order_review",
}

ORDER_CONTEXT_INTENTS = {
    "order_query",
    "logistics_query",
    "ticket_query",
    "order_cancel",
    "shipment_urge",
    "refund_progress",
}

CUSTOMER_CONTEXT_INTENTS = {
    "order_query",
    "recent_orders",
    "purchase_history",
    "order_cancel",
    "shipment_urge",
    "refund_progress",
    "logistics_query",
    "ticket_query",
    "aftersale_check",
    "ticket_create",
}


def _is_unknown_route(intent: str, error: str | None) -> bool:
    return intent == "unknown" or bool(error and "暂时无法识别你的需求" in error)


def _is_new_ticket_create_request(user_query: str, memory: SessionMemory) -> bool:
    """
    判断用户是否在开启一个新的“创建售后工单”流程。

    关键修正：
    上一轮 pending_action 可能是 aftersale_check；
    如果下一轮用户说“我要申请退货，原因是...”，应该切换为 ticket_create，
    不能继续停留在 aftersale_check。
    """

    if not memory.pending_action:
        return False

    if memory.pending_action.intent == "ticket_create":
        return False

    return bool(extract_ticket_type(user_query) and is_create_ticket_request(user_query))


def _basic_chat_fallback(user_query: str) -> str:
    text = user_query.strip()

    if text.lower() in {"你好", "您好", "hi", "hello"}:
        return "你好，我是电商售后与运营 Agent 助手。我可以帮你查询订单、物流、商品信息，也可以处理售后政策、资格预判断和售后工单。"

    if "你是谁" in text or "你是什么" in text or "你叫什么" in text:
        return "我是电商售后与运营 Agent 助手，主要负责商品咨询、订单查询、物流跟踪、售后政策解释、售后资格预判断和售后工单生成。"

    if "你能做什么" in text or "有什么功能" in text or "怎么使用" in text:
        return build_capability_reply()

    if "人工客服" in text or "转人工" in text or "真人客服" in text:
        return "如果涉及退款赔付、质量争议、高价值商品、特殊类目或对规则判断结果有异议，建议转人工客服进一步处理。"

    return "我主要负责电商售后与运营相关问题。你可以咨询商品、订单、物流、退换货政策、售后工单或运营数据。"


def _friendly_error_reply(user_query: str, route: dict[str, Any], memory: SessionMemory) -> str:
    error = route.get("error") or "你的问题还缺少必要信息。"

    prompt = f"""
用户问题：
{user_query}

系统判断：
{error}

当前会话上下文：
{memory.build_memory_summary()}

请你作为电商客服助手，礼貌地提醒用户补充必要信息。

要求：
1. 回复自然，不要机械。
2. 明确告诉用户缺少什么。
3. 如果当前会话中已有订单号，不要再次索要订单号。
4. 如果缺少退货原因，可以让用户补充原因，例如“不想要了、质量问题、发错货”等。
5. 如果缺少商品信息，可以提示用户补充商品名称或商品 ID。
6. 不要编造订单数据。
"""

    llm_result = chat_with_llm(
        prompt,
        temperature=0.3,
        max_tokens=300,
        fallback_content=error,
    )

    return llm_result["content"]


def _build_route_from_pending_input(user_query: str, memory: SessionMemory) -> dict[str, Any] | None:
    if not memory.pending_action:
        return None

    pending = memory.pending_action
    if pending.intent not in {"aftersale_check", "ticket_create", *ORDER_CONTEXT_INTENTS}:
        return None

    if pending.intent in ORDER_CONTEXT_INTENTS:
        if not is_only_order_id(user_query):
            return None

        arguments = dict(pending.arguments)
        arguments["order_id"] = user_query.strip()

        return {
            "intent": pending.intent,
            "tool_name": pending.tool_name or INTENT_TO_TOOL.get(pending.intent),
            "arguments": arguments,
            "error": None,
        }

    arguments = merge_aftersale_slots(
        base_arguments=pending.arguments,
        user_query=user_query,
        memory=memory,
        use_current_order=True,
    )

    missing = missing_aftersale_slots(arguments, pending.intent)
    if missing:
        return {
            "intent": pending.intent,
            "tool_name": None,
            "arguments": arguments,
            "error": build_aftersale_slot_reply(arguments, missing, pending.intent),
        }

    return {
        "intent": pending.intent,
        "tool_name": pending.tool_name or INTENT_TO_TOOL.get(pending.intent),
        "arguments": arguments,
        "error": None,
    }


def _recover_route_from_recent_history(user_query: str, memory: SessionMemory) -> dict[str, Any] | None:
    for turn in reversed(memory.history[-5:]):
        previous_query = turn.get("user_query") or ""
        ticket_type = extract_ticket_type(previous_query)

        if ticket_type and is_create_ticket_request(previous_query):
            intent = "ticket_create"
        elif ticket_type and is_check_question(previous_query):
            intent = "aftersale_check"
        else:
            continue

        base_arguments = {"ticket_type": ticket_type, "raw_reason": previous_query}
        arguments = merge_aftersale_slots(base_arguments, user_query, memory, use_current_order=True)

        missing = missing_aftersale_slots(arguments, intent)
        if missing:
            return {
                "intent": intent,
                "tool_name": None,
                "arguments": arguments,
                "error": build_aftersale_slot_reply(arguments, missing, intent),
            }

        return {
            "intent": intent,
            "tool_name": INTENT_TO_TOOL[intent],
            "arguments": arguments,
            "error": None,
        }

    return None


def _complete_route_with_memory(
    user_query: str,
    route: dict[str, Any],
    memory: SessionMemory,
) -> tuple[dict[str, Any], bool]:
    used_memory = False
    intent = route.get("intent")
    error = route.get("error")
    customer_id = memory.current_customer_id or memory.current_business_context.get("customer_id")

    if intent == "screenshot_order_review":
        context = memory.current_business_context or {}
        evidence_ids: list[str] = []
        raw_ids = context.get("evidence_ids") or []
        if isinstance(raw_ids, list):
            evidence_ids.extend(str(x) for x in raw_ids if x)
        for item in context.get("evidence_files") or []:
            if isinstance(item, dict) and item.get("evidence_id"):
                evidence_ids.append(str(item["evidence_id"]))
        unique_ids: list[str] = []
        for item in evidence_ids:
            if item not in unique_ids:
                unique_ids.append(item)
        arguments = {**(route.get("arguments") or {}), "evidence_ids": unique_ids[:10]}
        if customer_id:
            arguments["customer_id"] = customer_id
        if memory.current_business_context.get("session_id"):
            arguments["session_id"] = memory.current_business_context.get("session_id")
        return {
            "intent": intent,
            "tool_name": INTENT_TO_TOOL[intent],
            "arguments": arguments,
            "error": None,
        }, bool(unique_ids)

    if intent in {"aftersale_check", "ticket_create"}:
        arguments = merge_aftersale_slots(
            base_arguments=route.get("arguments") or {},
            user_query=user_query,
            memory=memory,
            use_current_order=True,
        )
        if customer_id:
            arguments["customer_id"] = customer_id

        if customer_id and not arguments.get("order_id") and (
            arguments.get("product_id") or arguments.get("product_name")
        ):
            try:
                from tools.business_tools import find_customer_purchase

                purchase_result = find_customer_purchase(
                    customer_id,
                    product_id=arguments.get("product_id"),
                    product_name=arguments.get("product_name"),
                )
                purchase = purchase_result.get("purchase") or {}
                if purchase:
                    arguments["order_id"] = purchase.get("order_id")
                    arguments["product_id"] = purchase.get("product_id")
                    arguments.setdefault("product_name", purchase.get("product_name"))
            except Exception:
                pass

        missing = missing_aftersale_slots(arguments, intent)
        if missing:
            return {
                "intent": intent,
                "tool_name": None,
                "arguments": arguments,
                "error": build_aftersale_slot_reply(arguments, missing, intent),
            }, bool(arguments.get("order_id") == memory.current_order_id and memory.current_order_id)

        return {
            "intent": intent,
            "tool_name": INTENT_TO_TOOL[intent],
            "arguments": arguments,
            "error": None,
        }, bool(arguments.get("order_id") == memory.current_order_id and memory.current_order_id)

    if not error:
        if intent in CUSTOMER_CONTEXT_INTENTS and customer_id:
            arguments = {**(route.get("arguments") or {}), "customer_id": customer_id}
            return {**route, "arguments": arguments}, True
        return route, used_memory

    if not memory.current_order_id:
        return route, used_memory

    if intent in ORDER_CONTEXT_INTENTS:
        arguments = {**(route.get("arguments") or {}), "order_id": memory.current_order_id}
        if customer_id:
            arguments["customer_id"] = customer_id
        return {
            "intent": intent,
            "tool_name": INTENT_TO_TOOL[intent],
            "arguments": arguments,
            "error": None,
        }, True

    return route, used_memory


def _maybe_set_pending_action(route: dict[str, Any], memory: SessionMemory) -> None:
    if not route.get("error"):
        return

    intent = route.get("intent")
    if intent not in {"aftersale_check", "ticket_create", *ORDER_CONTEXT_INTENTS}:
        return

    missing_slots: list[str] = []
    error = route.get("error") or ""

    if "订单号" in error:
        missing_slots.append("order_id")
    if "售后类型" in error:
        missing_slots.append("ticket_type")
    if "原因" in error:
        missing_slots.append("reason")
    if "拆封" in error or "使用" in error:
        missing_slots.append("package_status")
    if "商品 ID" in error or "商品名称" in error:
        missing_slots.append("product_id")

    memory.set_pending_action(
        intent=intent,
        tool_name=INTENT_TO_TOOL.get(intent),
        arguments=route.get("arguments") or {},
        missing_slots=missing_slots,
    )


def _format_context_notice(used_memory: bool, memory: SessionMemory) -> str:
    if not used_memory or not memory.current_order_id:
        return ""
    return f"\n\n上下文说明：本次已自动沿用当前会话中的订单号 {memory.current_order_id}。"


def _return_fixed_domain_reply(
    user_query: str,
    route: dict[str, Any],
    memory_obj: SessionMemory,
    state: dict[str, Any],
    domain: dict[str, Any],
) -> dict[str, Any]:
    state["mode"] = f"{domain.get('category', 'domain')}_reply"
    state["used_llm"] = False
    state["final_answer"] = domain["reply"]

    memory_obj.append_turn(user_query, state["final_answer"], route["intent"], route["tool_name"])
    state["memory"] = memory_obj.to_dict()

    return state


def _build_route(user_query: str, memory_obj: SessionMemory) -> tuple[dict[str, Any], bool, dict[str, Any] | None]:
    plan_user_task(user_query, memory_obj)
    interrupted_by_new_ticket_create = _is_new_ticket_create_request(user_query, memory_obj)
    if interrupted_by_new_ticket_create:
        memory_obj.clear_pending_action()

    if not interrupted_by_new_ticket_create:
        pending_route = _build_route_from_pending_input(user_query, memory_obj)
        if pending_route is not None:
            if not pending_route.get("error"):
                memory_obj.clear_pending_action()
            return pending_route, True, None

        recovered_route = _recover_route_from_recent_history(user_query, memory_obj)
        if recovered_route is not None:
            if not recovered_route.get("error"):
                memory_obj.clear_pending_action()
            return recovered_route, True, None

    route = route_user_query(user_query)
    route = choose_route_for_task(route, user_query, memory_obj)
    route, used_memory = _complete_route_with_memory(user_query, route, memory_obj)

    if not _is_unknown_route(route["intent"], route["error"]):
        return route, used_memory, None

    domain = cast(dict[str, Any], check_domain_scope(user_query))
    if not domain["allowed"] or domain.get("reply"):
        return route, used_memory, domain

    llm_route = route_with_llm(user_query, memory_obj.build_memory_summary())
    if llm_route:
        llm_route, llm_used_memory = _complete_route_with_memory(user_query, llm_route, memory_obj)
        return llm_route, bool(used_memory or llm_used_memory), domain

    return route, used_memory, domain


def run_contextual_guarded_agent(
    user_query: str,
    memory: SessionMemory | dict[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(memory, dict):
        memory_obj = SessionMemory.from_dict(memory)
    elif isinstance(memory, SessionMemory):
        memory_obj = memory
    else:
        memory_obj = SessionMemory()

    memory_obj.update_from_user_query(user_query)

    route, used_memory, domain = _build_route(user_query, memory_obj)
    state = cast(dict[str, Any], build_initial_state(user_query, route, used_memory=used_memory))
    state["domain"] = domain
    task = get_task_state(memory_obj)
    state["task_plan"] = task.to_dict() if task else None

    if domain and not domain["allowed"]:
        state["mode"] = "domain_rejected"
        state["used_llm"] = False
        state["final_answer"] = domain["reply"] or "抱歉，这个问题不在当前电商售后与运营 Agent 的处理范围内。"
        memory_obj.append_turn(user_query, state["final_answer"], route["intent"], route["tool_name"])
        state["memory"] = memory_obj.to_dict()
        return state

    if domain and domain.get("reply"):
        return _return_fixed_domain_reply(user_query, route, memory_obj, state, domain)

    if _is_unknown_route(route["intent"], route["error"]):
        llm_result = chat_with_llm(user_query, fallback_content=_basic_chat_fallback(user_query))
        state["used_llm"] = True
        state["mode"] = "general_chat"
        state["final_answer"] = llm_result["content"]
        state["llm_error"] = llm_result["error"]
        memory_obj.append_turn(user_query, state["final_answer"], route["intent"], route["tool_name"])
        state["memory"] = memory_obj.to_dict()
        return state

    if route["error"]:
        _maybe_set_pending_action(route, memory_obj)

        if route["intent"] in {"aftersale_check", "ticket_create"}:
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
                state["final_answer"] = build_context_aware_followup(
                    missing_slots=missing_slots,
                    arguments=route.get("arguments") or {},
                    memory=memory_obj,
                    intent=route.get("intent"),
                )
            except Exception:
                state["final_answer"] = route["error"]
            state["used_llm"] = False
            state["mode"] = "aftersale_slot_missing"
        else:
            state["used_llm"] = True
            state["mode"] = "slot_missing"
            state["final_answer"] = _friendly_error_reply(user_query, route, memory_obj)

        memory_obj.append_turn(user_query, state["final_answer"], route["intent"], route["tool_name"])
        state["memory"] = memory_obj.to_dict()
        return state

    effective_arguments = build_effective_tool_arguments(route["intent"], route["arguments"])
    state["arguments"] = effective_arguments

    tool_result = execute_tool(route["tool_name"], effective_arguments)
    update_task_after_tool(
        memory_obj,
        intent=route["intent"],
        tool_name=route["tool_name"],
        arguments=effective_arguments,
        tool_result=tool_result,
    )
    state["tool_result"] = tool_result

    handled = handle_tool_result(
        intent=route["intent"],
        tool_name=route["tool_name"],
        arguments=effective_arguments,
        tool_result=tool_result,
        memory=memory_obj,
    )

    if handled:
        state["used_llm"] = False
        state["mode"] = handled.get("mode", "tool_result_handled")
        state["final_answer"] = append_next_best_actions(
            handled["final_answer"],
            recommend_next_actions(
                intent=route["intent"],
                arguments=effective_arguments,
                tool_result=tool_result,
                memory=memory_obj,
            ),
        )
        memory_obj.update_after_tool_call(route["intent"], route["tool_name"], effective_arguments, tool_result)
        memory_obj.append_turn(user_query, state["final_answer"], route["intent"], route["tool_name"])
        state["memory"] = memory_obj.to_dict()
        return state

    force_create = bool(route["arguments"].get("force_create", False))
    tool_result, human_review = apply_human_review_to_tool_result(
        intent=route["intent"],
        tool_result=tool_result,
        force_create=force_create,
    )

    template_answer = generate_answer(route["intent"], tool_result)
    template_answer = enrich_template_answer_with_rag(
        user_query=user_query,
        intent=route["intent"],
        template_answer=template_answer,
        tool_result=tool_result,
    )
    template_answer = f"{template_answer}{_format_context_notice(used_memory, memory_obj)}{format_human_review_notice(human_review)}"
    template_answer = append_next_best_actions(
        template_answer,
        recommend_next_actions(
            intent=route["intent"],
            arguments=effective_arguments,
            tool_result=tool_result,
            memory=memory_obj,
        ),
    )

    memory_obj.update_after_tool_call(route["intent"], route["tool_name"], effective_arguments, tool_result)
    memory_obj.clear_pending_action()

    state["tool_result"] = tool_result
    state["template_answer"] = template_answer
    state["human_review"] = human_review

    llm_result = rewrite_tool_answer(
        user_query=user_query,
        intent=route["intent"],
        tool_name=route["tool_name"],
        arguments=effective_arguments,
        tool_result=tool_result,
        template_answer=template_answer,
        human_review=human_review,
    )

    state["used_llm"] = True
    state["mode"] = "tool_call_with_fixed_aftersale_flow"
    state["llm_error"] = llm_result["error"]
    state["final_answer"] = llm_result["content"]
    state["final_answer"] = append_next_best_actions(
        state["final_answer"],
        recommend_next_actions(
            intent=route["intent"],
            arguments=effective_arguments,
            tool_result=tool_result,
            memory=memory_obj,
        ),
    )

    memory_obj.append_turn(user_query, state["final_answer"], route["intent"], route["tool_name"])
    state["memory"] = memory_obj.to_dict()

    return state
