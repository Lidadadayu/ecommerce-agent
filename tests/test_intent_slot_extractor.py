from __future__ import annotations

from agent.intent_slot_extractor import extract_intent_slots


def test_complex_exchange_request_extracts_slots_and_missing_order() -> None:
    result = extract_intent_slots("这个订单昨天刚到，但是我发现包装破了，想看看能不能换一个")

    assert result["intent"] == "aftersale_check"
    assert result["after_sale_type"] == "exchange"
    assert result["reason"] == "包装破损"
    assert result["need_slot_filling"] is True
    assert "order_id" in result["missing_slots"]
