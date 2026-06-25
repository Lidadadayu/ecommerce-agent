from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    user_query: str
    intent: str
    tool_name: str | None
    arguments: dict[str, Any]
    tool_result: dict[str, Any] | None
    template_answer: str | None
    final_answer: str
    error: str | None
    used_llm: bool
    used_memory: bool
    mode: str | None
    domain: dict[str, Any] | None
    human_review: dict[str, Any] | None
    llm_error: str | None
    memory: dict[str, Any] | None


def build_initial_state(user_query: str, route: dict[str, Any], used_memory: bool = False) -> AgentState:
    return {
        "user_query": user_query,
        "intent": route.get("intent", "unknown"),
        "tool_name": route.get("tool_name"),
        "arguments": route.get("arguments") or {},
        "tool_result": None,
        "template_answer": None,
        "final_answer": "",
        "error": route.get("error"),
        "used_llm": False,
        "used_memory": used_memory,
        "mode": None,
        "domain": None,
        "human_review": None,
        "llm_error": None,
        "memory": None,
    }
