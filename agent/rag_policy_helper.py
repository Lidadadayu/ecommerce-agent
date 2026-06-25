from __future__ import annotations

from typing import Any

from rag.rag_service import build_rag_context


ROBOT_VACUUM_RAG_INTENTS = {
    "robot_vacuum_search",
    "robot_vacuum_detail",
    "robot_vacuum_compare",
}

POLICY_KEYWORDS = [
    "政策",
    "规则",
    "售后",
    "退货",
    "退款",
    "换货",
    "维修",
    "无理由",
    "质量问题",
    "人工审核",
    "包装",
    "拆封",
    "凭证",
]


def should_use_policy_rag(intent: str | None, user_query: str) -> bool:
    if intent == "policy_query":
        return True

    if intent in ROBOT_VACUUM_RAG_INTENTS:
        return True

    if intent in {"aftersale_check", "ticket_create"}:
        return True

    return any(keyword in user_query for keyword in POLICY_KEYWORDS)


def _extract_category_from_tool_result(tool_result: dict[str, Any] | None) -> str | None:
    if not isinstance(tool_result, dict):
        return None

    result = tool_result.get("result")
    if not isinstance(result, dict):
        return None

    # policy_query
    policies = result.get("policies")
    if isinstance(policies, list) and policies:
        category = policies[0].get("category")
        if category:
            return str(category)

    # aftersale_check
    rule_result = result.get("rule_result")
    if isinstance(rule_result, dict) and rule_result.get("category"):
        return str(rule_result["category"])

    eligibility = result.get("eligibility")
    if isinstance(eligibility, dict):
        nested_rule = eligibility.get("rule_result")
        if isinstance(nested_rule, dict) and nested_rule.get("category"):
            return str(nested_rule["category"])

    return None


def enrich_template_answer_with_rag(
    *,
    user_query: str,
    intent: str | None,
    template_answer: str,
    tool_result: dict[str, Any] | None = None,
    top_k: int = 3,
) -> str:
    """
    将 RAG 检索结果作为“知识库补充”拼接到模板答案后。

    设计原则：
    - 不推翻工具结论。
    - 只补充政策解释和 FAQ。
    - 最终仍交给 rewrite_tool_answer 润色。
    """

    if not should_use_policy_rag(intent, user_query):
        return template_answer

    category = _extract_category_from_tool_result(tool_result)
    rag_context = build_rag_context(user_query, category=category, top_k=top_k)

    if not rag_context:
        return template_answer

    return (
        f"{template_answer}\n\n"
        f"【知识库补充材料，仅用于解释政策，不替代订单工具判断】\n"
        f"{rag_context}"
    )
