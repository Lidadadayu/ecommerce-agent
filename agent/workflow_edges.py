from __future__ import annotations

from typing import Literal

from agent.graph_state import EcommerceGraphState


RouteBranch = Literal[
    "fixed_domain_response",
    "general_chat_response",
    "slot_missing_response",
    "tool_call",
]

ToolResultBranch = Literal[
    "handled_tool_response",
    "human_review",
]


def _is_unknown_route(intent: str | None, error: str | None) -> bool:
    return intent == "unknown" or bool(error and "暂时无法识别你的需求" in error)


def route_after_routing(state: EcommerceGraphState) -> RouteBranch:
    """
    routing_node 后的条件分支。

    分支逻辑：
    1. 越界/固定回复 → fixed_domain_response
    2. unknown → general_chat_response
    3. 缺槽/参数错误 → slot_missing_response
    4. 正常业务 → tool_call
    """

    route = state.get("route") or {}
    domain = state.get("domain")
    intent = route.get("intent")
    error = route.get("error")

    if domain and (not domain.get("allowed", True) or domain.get("reply")):
        return "fixed_domain_response"

    if _is_unknown_route(intent, error):
        return "general_chat_response"

    if error:
        return "slot_missing_response"

    return "tool_call"


def route_after_tool_result(state: EcommerceGraphState) -> ToolResultBranch:
    """
    tool_result_handler_node 后的条件分支。
    """

    if state.get("handled_result"):
        return "handled_tool_response"

    return "human_review"
