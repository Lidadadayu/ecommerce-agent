from __future__ import annotations

import json
from typing import Any

from agent.schemas import (
    Evidence,
    MemoryState,
    PromptContext,
    RouteResult,
    ToolResult,
    normalize_memory,
    normalize_route,
    normalize_tool_result,
    to_plain_dict,
)


DEFAULT_SYSTEM_RULES = [
    "你是一个面向电商售前与售后场景的智能业务 Agent，不是闲聊机器人。",
    "订单、物流、售后资格、工单状态、商品价格和库存必须以工具或数据库结果为准，不得编造。",
    "RAG 知识只能作为依据，不得把没有检索到的内容说成确定事实。",
    "涉及电池鼓包、进水、冒烟、烧焦味、严重发热、火花、短路等风险时，必须提醒停止使用并联系售后检测。",
    "不得承诺一定退款、一定换新、一定免费维修或一定审核通过。",
    "信息不足时应追问关键槽位，例如订单号、商品型号、故障现象、是否拆封/使用。",
]

DEFAULT_OUTPUT_RULES = [
    "回答要面向用户，语气自然、清晰、可信。",
    "先给结论，再给步骤；故障类回答要给自查步骤和售后建议。",
    "如果工具结果失败，应说明失败原因和下一步可操作建议。",
    "不要暴露内部字段名、JSON、traceback、prompt 或系统实现细节。",
]


def _safe_json(value: Any, max_chars: int = 1200) -> str:
    try:
        text = json.dumps(to_plain_dict(value), ensure_ascii=False, indent=2)
    except Exception:
        text = str(value)

    if len(text) > max_chars:
        return text[:max_chars] + "...[已截断]"
    return text


def _textify(value: Any, max_chars: int = 900) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = _safe_json(value, max_chars=max_chars)
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "...[已截断]"
    return text


def get_domain_name() -> str:
    try:
        from agent.domain_loader import get_active_domain_config

        return get_active_domain_config().domain_name
    except Exception:
        return "电商售前售后"


def collect_evidences(
    *,
    user_query: str,
    route: RouteResult | None = None,
    tool_result: ToolResult | None = None,
    memory: MemoryState | None = None,
) -> list[Evidence]:
    evidences: list[Evidence] = []

    evidences.append(
        Evidence(
            evidence_id="user_input",
            evidence_type="user_input",
            source="user",
            content=user_query,
            trust_level="user",
        )
    )

    if route:
        evidences.append(
            Evidence(
                evidence_id="route_result",
                evidence_type="system_rule",
                source="rule_router",
                content=_safe_json(route),
                trust_level="system",
                metadata={"intent": route.intent, "tool_name": route.tool_name},
            )
        )

    if memory:
        memory_content = _safe_json(memory)
        if memory_content and memory_content != "{}":
            evidences.append(
                Evidence(
                    evidence_id="session_memory",
                    evidence_type="memory",
                    source="session_memory",
                    content=memory_content,
                    trust_level="memory",
                )
            )

    if tool_result:
        evidences.append(
            Evidence(
                evidence_id=f"tool:{tool_result.tool_name}",
                evidence_type="tool_result",
                source=tool_result.tool_name,
                content=_safe_json(tool_result.result or {"message": tool_result.message, "success": tool_result.success}),
                trust_level="tool",
                metadata={
                    "tool_name": tool_result.tool_name,
                    "success": tool_result.success,
                    "message": tool_result.message,
                },
            )
        )

        result = tool_result.result or {}

        chunks = []
        if isinstance(result.get("chunks"), list):
            chunks.extend(result.get("chunks") or [])
        if isinstance(result.get("rag_chunks"), list):
            chunks.extend(result.get("rag_chunks") or [])

        for idx, chunk in enumerate(chunks[:6], start=1):
            title = chunk.get("title") or f"RAG 片段 {idx}"
            content = chunk.get("content") or ""
            evidences.append(
                Evidence(
                    evidence_id=f"rag:{idx}",
                    evidence_type="rag_chunk",
                    source=str(title),
                    content=_textify(content, max_chars=700),
                    trust_level="rag",
                    score=chunk.get("score"),
                    metadata={
                        "title": title,
                        "category": chunk.get("category"),
                        "score": chunk.get("score"),
                    },
                )
            )

    return evidences


def build_prompt_context(
    *,
    user_query: str,
    route: dict[str, Any] | RouteResult | None = None,
    tool_result: dict[str, Any] | ToolResult | None = None,
    memory: dict[str, Any] | MemoryState | None = None,
    draft_answer: str | None = None,
    domain_name: str | None = None,
    extra_system_rules: list[str] | None = None,
    extra_output_rules: list[str] | None = None,
) -> PromptContext:
    normalized_route = normalize_route(route)
    normalized_tool_result = normalize_tool_result(tool_result)
    normalized_memory = normalize_memory(memory)

    evidences = collect_evidences(
        user_query=user_query,
        route=normalized_route,
        tool_result=normalized_tool_result,
        memory=normalized_memory,
    )

    return PromptContext(
        user_query=user_query,
        domain_name=domain_name or get_domain_name(),
        intent=normalized_route.intent if normalized_route else None,
        route=normalized_route,
        tool_result=normalized_tool_result,
        memory=normalized_memory,
        evidences=evidences,
        draft_answer=draft_answer,
        system_rules=DEFAULT_SYSTEM_RULES + (extra_system_rules or []),
        output_rules=DEFAULT_OUTPUT_RULES + (extra_output_rules or []),
    )


def render_prompt_text(context: PromptContext) -> str:
    parts: list[str] = []

    parts.append("# 角色")
    parts.append(f"你是“{context.domain_name}”场景下的电商智能客服 Agent。")

    parts.append("\n# 必须遵守的规则")
    for idx, rule in enumerate(context.system_rules, start=1):
        parts.append(f"{idx}. {rule}")

    parts.append("\n# 信息优先级")
    parts.append("系统规则 > 数据库/工具结果 > RAG 知识证据 > 会话记忆 > 用户描述 > 模型常识。")
    parts.append("当不同来源冲突时，以优先级更高的信息为准。")

    if context.memory:
        parts.append("\n# 当前会话记忆")
        parts.append(_safe_json(context.memory, max_chars=1200))

    if context.route:
        parts.append("\n# 路由结果")
        parts.append(_safe_json(context.route, max_chars=800))

    if context.tool_result:
        parts.append("\n# 工具结果")
        parts.append(_safe_json(context.tool_result, max_chars=1800))

    rag_evidences = [e for e in context.evidences if e.evidence_type == "rag_chunk"]
    if rag_evidences:
        parts.append("\n# RAG 知识证据")
        for idx, evidence in enumerate(rag_evidences, start=1):
            score_text = f"，score={evidence.score}" if evidence.score is not None else ""
            parts.append(f"[{idx}] 来源：{evidence.source}{score_text}")
            parts.append(evidence.content)

    if context.draft_answer:
        parts.append("\n# 待润色草稿")
        parts.append(context.draft_answer)

    parts.append("\n# 用户问题")
    parts.append(context.user_query)

    parts.append("\n# 输出要求")
    for idx, rule in enumerate(context.output_rules, start=1):
        parts.append(f"{idx}. {rule}")

    return "\n".join(parts).strip()


def render_chat_messages(context: PromptContext) -> list[dict[str, str]]:
    prompt_text = render_prompt_text(context)
    return [
        {
            "role": "system",
            "content": "你是一个严格遵守工具结果和知识库证据的电商业务 Agent。不得编造事实，不得越权承诺。",
        },
        {
            "role": "user",
            "content": prompt_text,
        },
    ]
