from __future__ import annotations

import re
from typing import Any

from agent.schemas import GuardIssue, GuardResult, PromptContext, normalize_tool_result


PROMISE_PATTERNS = [
    r"一定(?:可以|能|会)",
    r"肯定(?:可以|能|会|是)",
    r"保证(?:退款|退货|换新|维修|通过)",
    r"必定(?:退款|退货|换新|维修|通过)",
    r"免费(?:换新|维修|退货)",
    r"直接(?:退款|退货|换新)",
]

UNSAFE_REPAIR_PATTERNS = [
    r"自行拆(?:机|开)",
    r"自己拆(?:机|开)",
    r"打开主板",
    r"拆开电池",
    r"短接",
    r"直接更换主板",
    r"继续充电观察",
]

HIGH_RISK_WORDS = [
    "烧焦",
    "焦味",
    "冒烟",
    "进水",
    "泡水",
    "电池鼓包",
    "鼓包",
    "漏液",
    "火花",
    "短路",
    "严重发热",
]

SAFETY_REQUIRED_WORDS = [
    "停止使用",
    "不要继续充电",
    "不要自行拆机",
    "联系售后",
    "售后检测",
]


def _match_any(text: str, patterns: list[str]) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        if re.search(pattern, text):
            hits.append(pattern)
    return hits


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _tool_result_failed(context: PromptContext | None) -> bool:
    if not context or not context.tool_result:
        return False
    return not context.tool_result.success


def _tool_says_ineligible(context: PromptContext | None) -> bool:
    if not context or not context.tool_result:
        return False

    result = context.tool_result.result or {}
    if result.get("eligible") is False:
        return True

    message = str(result.get("message") or context.tool_result.message or "")
    return any(word in message for word in ["不满足", "不能", "不支持", "未通过", "失败"])


def _has_rag_evidence(context: PromptContext | None) -> bool:
    if not context:
        return False
    return any(e.evidence_type == "rag_chunk" for e in context.evidences)


def guard_answer(answer: str, context: PromptContext | None = None) -> GuardResult:
    answer = answer or ""
    issues: list[GuardIssue] = []

    promise_hits = _match_any(answer, PROMISE_PATTERNS)
    if promise_hits:
        issues.append(
            GuardIssue(
                code="over_promise",
                severity="high",
                message=f"回答中存在可能越权承诺的表达：{promise_hits}",
                suggestion="改成“可以协助申请/建议提交/以审核结果为准”。",
            )
        )

    unsafe_hits = _match_any(answer, UNSAFE_REPAIR_PATTERNS)
    if unsafe_hits:
        issues.append(
            GuardIssue(
                code="unsafe_repair_instruction",
                severity="high",
                message=f"回答中存在不安全维修建议：{unsafe_hits}",
                suggestion="删除自行拆机、短接、更换主板等建议，改为停止使用并联系售后。",
            )
        )

    if context and _contains_any(context.user_query, HIGH_RISK_WORDS):
        if not _contains_any(answer, SAFETY_REQUIRED_WORDS):
            issues.append(
                GuardIssue(
                    code="missing_safety_notice",
                    severity="high",
                    message="用户问题包含高风险词，但回答缺少停止使用/不要充电/联系售后的安全提醒。",
                    suggestion="加入明确安全提醒。",
                )
            )

    if _tool_says_ineligible(context):
        risky_positive = any(word in answer for word in ["可以退", "可以换", "可以维修", "可以退款", "已经通过", "没问题"])
        if risky_positive:
            issues.append(
                GuardIssue(
                    code="contradict_tool_result",
                    severity="high",
                    message="工具结果显示不满足或失败，但回答中出现了正向承诺。",
                    suggestion="以工具结果为准，说明暂不满足或需要人工审核。",
                )
            )

    if _tool_result_failed(context):
        if any(word in answer for word in ["已成功", "已经创建", "已经取消", "已退款", "已完成"]):
            issues.append(
                GuardIssue(
                    code="false_success_claim",
                    severity="high",
                    message="工具调用失败，但回答中出现成功处理表述。",
                    suggestion="说明工具失败原因，并给出下一步建议。",
                )
            )

    if context and context.intent and "knowledge" in context.intent:
        if not _has_rag_evidence(context) and any(word in answer for word in ["根据政策", "知识库显示", "规定为", "标准是"]):
            issues.append(
                GuardIssue(
                    code="unsupported_knowledge_claim",
                    severity="medium",
                    message="知识类回答缺少 RAG 证据，但出现了确定性依据表述。",
                    suggestion="改为说明当前知识库未检索到足够依据。",
                )
            )

    repaired = repair_answer(answer, issues, context)
    return GuardResult(ok=len([i for i in issues if i.severity in {"medium", "high"}]) == 0, issues=issues, repaired_answer=repaired)


def repair_answer(answer: str, issues: list[GuardIssue], context: PromptContext | None = None) -> str:
    if not issues:
        return answer

    repaired = answer or ""

    for pattern in PROMISE_PATTERNS:
        repaired = re.sub(pattern, "可以协助申请，最终以平台规则和审核结果为准", repaired)

    unsafe_replacements = [
        ("自行拆机", "不要自行拆机"),
        ("自己拆机", "不要自行拆机"),
        ("打开主板", "不要自行打开主板"),
        ("拆开电池", "不要自行拆开电池"),
        ("继续充电观察", "停止使用并联系售后检测"),
    ]
    for old, new in unsafe_replacements:
        repaired = repaired.replace(old, new)

    codes = {issue.code for issue in issues}

    if "missing_safety_notice" in codes:
        notice = "安全提醒：当前情况可能涉及用电或电池安全风险，建议立即停止使用，不要继续充电或自行拆机，并联系售后检测。"
        if notice not in repaired:
            repaired = notice + "\n\n" + repaired

    if "contradict_tool_result" in codes:
        repaired += "\n\n补充说明：售后资格和处理结果应以订单工具、平台规则和人工审核结果为准。"

    if "false_success_claim" in codes:
        repaired += "\n\n补充说明：当前工具调用未确认成功，请以系统实际处理结果为准，必要时转人工客服。"

    if "unsupported_knowledge_claim" in codes:
        repaired += "\n\n补充说明：当前知识库证据不足，建议补充型号、故障现象或订单号后继续判断。"

    return repaired.strip()


def enforce_answer_policy(answer: str, context: PromptContext | None = None) -> str:
    return guard_answer(answer, context).repaired_answer or answer
