from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal


TrustLevel = Literal["system", "database", "tool", "rag", "memory", "user", "llm"]
EvidenceType = Literal["tool_result", "rag_chunk", "memory", "user_input", "system_rule"]


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def to_plain_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, dict):
        return {str(k): to_plain_dict(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_plain_dict(v) for v in value]
    if isinstance(value, tuple):
        return [to_plain_dict(v) for v in value]
    return value


@dataclass
class Evidence:
    """
    统一证据结构。

    Agent 回答不应该只依赖 LLM 自身知识，而应尽量依赖工具、数据库、RAG 和记忆。
    trust_level 用于描述信息可信度，后续 answer_guard 会据此做回答约束。
    """

    evidence_id: str
    evidence_type: EvidenceType
    source: str
    content: str
    trust_level: TrustLevel
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteResult:
    intent: str
    tool_name: str | None
    arguments: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    message: str = ""
    result: dict[str, Any] | None = None
    trusted: bool = True


@dataclass
class MemoryState:
    """
    标准化会话记忆。

    current_order_id/current_product_id 是当前业务上下文。
    pending_action 用于缺槽追问。
    summary 用于长对话压缩。
    user_profile 是长期偏好或用户画像摘要。
    """

    session_id: str | None = None
    current_order_id: str | None = None
    current_product_id: str | None = None
    current_intent: str | None = None
    pending_action: dict[str, Any] | None = None
    summary: str | None = None
    user_profile: dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=now_str)


@dataclass
class PromptContext:
    """
    LLM 上下文工程的统一输入。
    """

    user_query: str
    domain_name: str = "电商售前售后"
    intent: str | None = None
    route: RouteResult | None = None
    tool_result: ToolResult | None = None
    memory: MemoryState | None = None
    evidences: list[Evidence] = field(default_factory=list)
    draft_answer: str | None = None
    system_rules: list[str] = field(default_factory=list)
    output_rules: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_str)


@dataclass
class GuardIssue:
    code: str
    severity: Literal["low", "medium", "high"]
    message: str
    suggestion: str | None = None


@dataclass
class GuardResult:
    ok: bool
    issues: list[GuardIssue] = field(default_factory=list)
    repaired_answer: str | None = None


def normalize_route(route: dict[str, Any] | RouteResult | None) -> RouteResult | None:
    if route is None:
        return None
    if isinstance(route, RouteResult):
        return route
    return RouteResult(
        intent=str(route.get("intent") or "unknown"),
        tool_name=route.get("tool_name"),
        arguments=route.get("arguments") or {},
        error=route.get("error"),
    )


def normalize_tool_result(tool_result: dict[str, Any] | ToolResult | None) -> ToolResult | None:
    if tool_result is None:
        return None
    if isinstance(tool_result, ToolResult):
        return tool_result
    return ToolResult(
        tool_name=str(tool_result.get("tool_name") or ""),
        success=bool(tool_result.get("success")),
        message=str(tool_result.get("message") or ""),
        result=tool_result.get("result") if isinstance(tool_result.get("result"), dict) else None,
        trusted=True,
    )


def normalize_memory(memory: dict[str, Any] | MemoryState | None) -> MemoryState | None:
    if memory is None:
        return None
    if isinstance(memory, MemoryState):
        return memory

    pending = memory.get("pending_action") or memory.get("pending")
    user_profile = memory.get("user_profile") or memory.get("profile") or {}

    return MemoryState(
        session_id=memory.get("session_id"),
        current_order_id=memory.get("current_order_id") or memory.get("order_id"),
        current_product_id=memory.get("current_product_id") or memory.get("product_id"),
        current_intent=memory.get("current_intent"),
        pending_action=pending if isinstance(pending, dict) else None,
        summary=memory.get("summary") or memory.get("conversation_summary"),
        user_profile=user_profile if isinstance(user_profile, dict) else {},
        updated_at=memory.get("updated_at") or now_str(),
    )
