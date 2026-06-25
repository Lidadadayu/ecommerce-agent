from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any


QUALITY_WORDS = ["质量", "坏", "损坏", "破损", "无法", "不能", "故障", "失灵", "不启动", "不工作", "异常", "漏发", "少件", "瑕疵"]


@dataclass
class AftersalePolicyDecision:
    decision: str
    eligible: bool
    reason: str
    matched_rules: list[str]
    rule_result: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "eligible": self.eligible,
            "reason": self.reason,
            "matched_rules": self.matched_rules,
            "rule_result": self.rule_result,
        }


def detect_quality_issue(reason: str | None) -> bool:
    return bool(reason) and any(word in reason for word in QUALITY_WORDS)


def _manual_review_threshold() -> float:
    try:
        return float(os.getenv("AFTERSALE_MANUAL_REVIEW_AMOUNT_THRESHOLD", os.getenv("HUMAN_REVIEW_AMOUNT_THRESHOLD", "1000")))
    except ValueError:
        return 1000.0


def evaluate_aftersale_policy(
    *,
    order: dict[str, Any],
    item: dict[str, Any],
    policy: dict[str, Any],
    ticket_type: str,
    reason: str,
    receive_time: datetime,
    application_time: datetime,
    package_complete: bool = True,
    has_quality_issue: bool | None = None,
) -> AftersalePolicyDecision:
    matched_rules: list[str] = ["ORDER_EXISTS", "PRODUCT_IN_ORDER"]
    has_quality_issue = detect_quality_issue(reason) if has_quality_issue is None else has_quality_issue
    elapsed_days_float = (application_time - receive_time).total_seconds() / 86400
    elapsed_days = int(elapsed_days_float)
    category = item.get("category")
    allow_days = policy.get("allow_days")
    cond = policy.get("conditions") or {}

    base = {
        "eligible": False,
        "order_id": order.get("order_id"),
        "product_id": item.get("product_id"),
        "category": category,
        "ticket_type": ticket_type,
        "policy_title": policy.get("title"),
        "allow_days": allow_days,
        "elapsed_days": elapsed_days,
        "receive_time": str(receive_time),
        "application_time": str(application_time),
        "has_quality_issue": has_quality_issue,
        "package_complete": package_complete,
    }

    if order.get("order_status") != "delivered":
        matched_rules.append("ORDER_NOT_DELIVERED")
        return AftersalePolicyDecision("reject", False, "订单未签收或未完成，不满足售后申请条件", matched_rules, {**base, "order_status": order.get("order_status"), "reason": "订单未签收或未完成，不满足售后申请条件"})

    matched_rules.append("ORDER_DELIVERED")

    if elapsed_days_float < 0:
        matched_rules.append("APPLICATION_BEFORE_RECEIVE")
        return AftersalePolicyDecision("reject", False, "申请时间早于签收时间", matched_rules, {**base, "reason": "申请时间早于签收时间"})

    if cond.get("no_reason_return", True) is False and not has_quality_issue:
        matched_rules.append("NO_REASON_NOT_SUPPORTED")
        return AftersalePolicyDecision("reject", False, "该商品类别不支持无理由售后", matched_rules, {**base, "reason": "该商品类别不支持无理由售后"})

    if cond.get("quality_issue_required", False) and not has_quality_issue:
        matched_rules.append("QUALITY_ISSUE_REQUIRED")
        return AftersalePolicyDecision("reject", False, "政策要求存在质量问题，但申请原因未体现质量问题", matched_rules, {**base, "reason": "政策要求存在质量问题，但申请原因未体现质量问题"})

    if cond.get("must_unused", False) and not package_complete:
        matched_rules.append("PACKAGE_INCOMPLETE")
        return AftersalePolicyDecision("reject", False, "包装或配件不完整", matched_rules, {**base, "reason": "包装或配件不完整"})

    if allow_days is not None and elapsed_days_float > allow_days:
        matched_rules.append("AFTERSALE_WINDOW_EXPIRED")
        return AftersalePolicyDecision("reject", False, "超过售后允许期限", matched_rules, {**base, "reason": "超过售后允许期限"})

    if allow_days is not None:
        matched_rules.append(f"{ticket_type.upper()}_WITHIN_{allow_days}_DAYS")
    if has_quality_issue:
        matched_rules.append("QUALITY_ISSUE_DETECTED")

    decision = "approve"
    reason_text = "满足售后政策要求"
    payment_amount = float(order.get("payment_amount") or 0)
    if payment_amount >= _manual_review_threshold():
        decision = "manual_review"
        reason_text = "订单金额超过人工审核阈值，需要人工客服确认"
        matched_rules.append("HIGH_AMOUNT_REVIEW")

    return AftersalePolicyDecision(decision, True, reason_text, matched_rules, {**base, "eligible": True, "decision": decision, "matched_rules": matched_rules, "payment_amount": payment_amount, "reason": reason_text})
