from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

from agent.constants import ticket_type_display
from database.db import execute_write
from tools.business_tools import get_order_detail

HIGH_RISK_CATEGORIES = {"家用电器", "生鲜食品", "虚拟商品", "手机数码", "电脑办公", "大家电", "家具", "珠宝", "奢侈品"}
HIGH_RISK_TICKET_TYPES = {"refund", "repair"}
QUALITY_WORDS = ["质量", "损坏", "破损", "无法", "不能", "故障", "失灵", "异常", "瑕疵"]


def _amount_threshold() -> float:
    try:
        return float(os.getenv("HUMAN_REVIEW_AMOUNT_THRESHOLD", "1000"))
    except ValueError:
        return 1000.0


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _contains_quality_issue(reason: str | None) -> bool:
    return bool(reason) and any(w in reason for w in QUALITY_WORDS)


def _find_order_item(order: dict[str, Any], product_id: str | None) -> dict[str, Any] | None:
    items = order.get("items", [])
    if product_id:
        for item in items:
            if item.get("product_id") == product_id:
                return item
    return items[0] if len(items) == 1 else None


def assess_human_review_need(order_id: str, product_id: str | None = None, ticket_type: str | None = None, reason: str | None = None, eligibility: dict[str, Any] | None = None, force_create: bool = False) -> dict[str, Any]:
    review_reasons = []
    threshold = _amount_threshold()
    order_result = get_order_detail(order_id)
    if not order_result.get("success"):
        return {"requires_human_review": True, "review_level": "high", "review_reasons": ["订单信息查询失败，需要人工确认"], "policy": "agent_must_not_make_final_decision"}

    order = order_result["order"]
    item = _find_order_item(order, product_id)
    payment_amount = _to_float(order.get("payment_amount"))
    category = item.get("category") if item else None
    ticket_name = ticket_type_display(ticket_type)

    if payment_amount >= threshold:
        review_reasons.append(f"订单金额 {payment_amount:.2f} 元达到人工审核阈值 {threshold:.2f} 元")
    if category in HIGH_RISK_CATEGORIES:
        review_reasons.append(f"商品类别为高风险或特殊类目：{category}")
    if ticket_type in HIGH_RISK_TICKET_TYPES:
        review_reasons.append(f"售后类型“{ticket_name}”需要人工客服复核")
    if force_create:
        review_reasons.append("该工单为强制创建，必须人工审核")
    if _contains_quality_issue(reason):
        review_reasons.append("申请原因涉及质量问题，需要人工确认凭证或商品状态")
    if eligibility:
        rule_result = eligibility.get("rule_result") or {}
        if eligibility.get("eligible") is False:
            review_reasons.append("规则判断为不满足条件，如仍继续处理必须人工审核")
        if rule_result.get("has_quality_issue"):
            review_reasons.append("规则识别到质量问题，需要人工确认证据")

    requires = bool(review_reasons)
    return {
        "requires_human_review": requires,
        "review_level": "high" if requires else "normal",
        "review_reasons": review_reasons,
        "policy": "Agent 仅进行售后资格预判断和工单生成，不直接做最终退货、退款、赔付或维修结论。",
        "order_id": order_id,
        "product_id": product_id,
        "ticket_type": ticket_type,
        "ticket_type_name": ticket_name,
        "category": category,
        "payment_amount": payment_amount,
    }


def mark_ticket_pending_review(ticket_id: str) -> None:
    execute_write(
        """
        UPDATE aftersale_tickets
        SET ticket_status = 'pending_review', updated_at = CURRENT_TIMESTAMP
        WHERE ticket_id = :ticket_id
        """,
        {"ticket_id": ticket_id},
    )


def format_human_review_notice(review: dict[str, Any] | None) -> str:
    if not review:
        return ""
    if not review.get("requires_human_review"):
        return "\n\n补充说明：当前仅表示系统完成了规则预判断，最终售后处理仍以平台审核结果为准。"
    reasons = review.get("review_reasons") or []
    reason_text = "；".join(reasons) if reasons else "该场景需要人工客服进一步确认"
    return (
        "\n\n人工审核提示：该申请需要人工客服进一步审核。"
        f"\n原因：{reason_text}。"
        "\n请注意，智能体不会直接决定最终退货、退款、赔付或维修结果。"
    )


def apply_human_review_to_tool_result(intent: str, tool_result: dict[str, Any], force_create: bool = False) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if intent not in {"aftersale_check", "ticket_create"}:
        return tool_result, None
    outer = tool_result.get("result") or {}
    if not isinstance(outer, dict):
        return tool_result, None

    if intent == "aftersale_check":
        eligibility = outer
        rule = eligibility.get("rule_result") or {}
        order_id = rule.get("order_id")
        if not order_id:
            return tool_result, None
        review = assess_human_review_need(order_id, rule.get("product_id"), rule.get("ticket_type"), rule.get("reason"), eligibility, force_create)
        outer["human_review"] = review
        return tool_result, review

    eligibility = outer.get("eligibility") or {}
    ticket = outer.get("ticket") or {}
    rule = eligibility.get("rule_result") or {}
    order_id = rule.get("order_id") or ticket.get("order_id")
    if not order_id:
        return tool_result, None
    review = assess_human_review_need(order_id, rule.get("product_id") or ticket.get("product_id"), rule.get("ticket_type") or ticket.get("ticket_type"), ticket.get("reason"), eligibility, force_create)
    outer["human_review"] = review
    if outer.get("success") and review.get("requires_human_review") and ticket.get("ticket_id"):
        mark_ticket_pending_review(ticket["ticket_id"])
        ticket["ticket_status"] = "pending_review"
    return tool_result, review
