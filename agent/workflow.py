from __future__ import annotations

from functools import lru_cache
from typing import Any

from agent.graph_state import EcommerceGraphState


def _fallback_run_agent(user_query: str, memory: dict[str, Any] | None = None) -> dict[str, Any]:
    from agent.legacy_agent import run_contextual_guarded_agent

    return run_contextual_guarded_agent(user_query=user_query, memory=memory)


@lru_cache(maxsize=1)
def build_graph():
    """
    构建 LangGraph 多节点编排图。

    如果运行环境未安装 langgraph，请使用 run_graph_agent 的 fallback。
    """

    from langgraph.graph import END, START, StateGraph

    from agent.workflow_nodes import (
        fixed_domain_response_node,
        general_chat_response_node,
        handled_tool_response_node,
        human_review_node,
        initialize_node,
        response_rewrite_node,
        routing_node,
        slot_missing_response_node,
        tool_call_node,
        tool_result_handler_node,
    )
    from agent.workflow_edges import route_after_routing, route_after_tool_result

    workflow = StateGraph(EcommerceGraphState)

    workflow.add_node("initialize", initialize_node)
    workflow.add_node("routing", routing_node)
    workflow.add_node("fixed_domain_response", fixed_domain_response_node)
    workflow.add_node("general_chat_response", general_chat_response_node)
    workflow.add_node("slot_missing_response", slot_missing_response_node)
    workflow.add_node("tool_call", tool_call_node)
    workflow.add_node("tool_result_handler", tool_result_handler_node)
    workflow.add_node("handled_tool_response", handled_tool_response_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("response_rewrite", response_rewrite_node)

    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", "routing")

    workflow.add_conditional_edges(
        "routing",
        route_after_routing,
        {
            "fixed_domain_response": "fixed_domain_response",
            "general_chat_response": "general_chat_response",
            "slot_missing_response": "slot_missing_response",
            "tool_call": "tool_call",
        },
    )

    workflow.add_edge("tool_call", "tool_result_handler")

    workflow.add_conditional_edges(
        "tool_result_handler",
        route_after_tool_result,
        {
            "handled_tool_response": "handled_tool_response",
            "human_review": "human_review",
        },
    )

    workflow.add_edge("human_review", "response_rewrite")

    workflow.add_edge("fixed_domain_response", END)
    workflow.add_edge("general_chat_response", END)
    workflow.add_edge("slot_missing_response", END)
    workflow.add_edge("handled_tool_response", END)
    workflow.add_edge("response_rewrite", END)

    return workflow.compile()


def run_graph_agent(
    user_query: str,
    memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    前端可直接调用的 LangGraph Agent 入口。

    返回结构仍保持和原 run_contextual_guarded_agent 一致：
    {
        "final_answer": "...",
        "memory": {...},
        "mode": "...",
        ...
    }
    """

    try:
        graph = build_graph()
    except Exception:
        return _fallback_run_agent(user_query=user_query, memory=memory)

    try:
        output = graph.invoke(
            {
                "user_query": user_query,
                "input_memory": memory,
            }
        )

        agent_state = output.get("agent_state")
        if isinstance(agent_state, dict):
            return agent_state

        return _fallback_run_agent(user_query=user_query, memory=memory)

    except Exception as exc:
        fallback_state = _fallback_run_agent(user_query=user_query, memory=memory)
        fallback_state["mode"] = "langgraph_fallback_after_error"
        fallback_state["graph_error"] = str(exc)
        return fallback_state
