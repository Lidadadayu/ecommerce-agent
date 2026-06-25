from __future__ import annotations

from agent.failure_recovery import build_recovery_reply, classify_tool_failure
from agent.followup_strategy import build_context_aware_followup
from agent.memory import SessionMemory
from agent.next_best_action import recommend_next_actions


def test_context_aware_followup_asks_only_next_key_slot() -> None:
    memory = SessionMemory(current_order_id="O202605010001")
    memory.current_business_context["order_id"] = "O202605010001"

    reply = build_context_aware_followup(
        missing_slots=["order_id", "reason", "package_status"],
        arguments={"ticket_type": "return", "order_id": "O202605010001"},
        memory=memory,
        intent="ticket_create",
    )

    assert "O202605010001" in reply
    assert "售后原因" in reply or "原因" in reply
    assert "订单号、" not in reply


def test_failure_recovery_classifies_order_not_found() -> None:
    failure = classify_tool_failure(
        intent="order_query",
        tool_name="order_query",
        arguments={"order_id": "O202605010009"},
        tool_result={"success": True, "result": {"success": False, "message": "未找到订单：O202605010009"}},
    )

    assert failure
    assert failure["failure_type"] == "order_not_found"
    reply = build_recovery_reply(failure, arguments={"order_id": "O202605010009"})
    assert "O202605010009" in reply


def test_next_best_action_for_delivered_logistics() -> None:
    actions = recommend_next_actions(
        intent="logistics_query",
        arguments={"order_id": "O202605010001"},
        tool_result={"success": True, "result": {"success": True, "current_status": "已签收"}},
    )

    assert any("退货" in item for item in actions)
