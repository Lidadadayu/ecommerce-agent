from __future__ import annotations

from datetime import datetime

from agent.aftersale_policy_engine import evaluate_aftersale_policy


def test_policy_engine_returns_manual_review_for_high_amount() -> None:
    decision = evaluate_aftersale_policy(
        order={"order_id": "O202606200001", "order_status": "delivered", "payment_amount": 1599},
        item={"product_id": "P10002", "category": "家用电器"},
        policy={"title": "家用电器 30 天维修", "allow_days": 30, "conditions": {"quality_issue_required": True}},
        ticket_type="repair",
        reason="扫地机器人无法启动，申请维修",
        receive_time=datetime(2026, 6, 22, 12, 0, 0),
        application_time=datetime(2026, 6, 24, 12, 0, 0),
        package_complete=False,
    )

    assert decision.eligible is True
    assert decision.decision == "manual_review"
    assert "HIGH_AMOUNT_REVIEW" in decision.matched_rules
