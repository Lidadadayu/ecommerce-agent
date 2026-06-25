from __future__ import annotations

from typing import Any, TypedDict


class EcommerceGraphState(TypedDict, total=False):
    """
    LangGraph 共享状态。

    注意：
    - 这里保存的是一次用户请求在图中的流转状态。
    - 真正返回给前端的是 agent_state。
    - memory_obj 是 SessionMemory 对象，只在图内部使用。
    """

    user_query: str
    input_memory: dict[str, Any] | None
    memory_obj: Any

    route: dict[str, Any]
    used_memory: bool
    domain: dict[str, Any] | None
    task_plan: dict[str, Any] | None

    effective_arguments: dict[str, Any]
    tool_result: dict[str, Any] | None
    handled_result: dict[str, Any] | None
    human_review: dict[str, Any] | None
    template_answer: str | None

    agent_state: dict[str, Any]
    error: str | None
