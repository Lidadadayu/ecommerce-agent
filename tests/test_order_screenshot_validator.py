from __future__ import annotations

from agent.order_screenshot_validator import validate_screenshot_against_order


def test_screenshot_validator_matches_database_fields(monkeypatch) -> None:
    def fake_get_order_detail(order_id: str, customer_id: str | None = None) -> dict:
        return {
            "success": True,
            "order": {
                "order_id": order_id,
                "order_status": "delivered",
                "payment_amount": 299.0,
                "items": [{"product_name": "无线蓝牙耳机 Pro"}],
            },
        }

    monkeypatch.setattr("agent.order_screenshot_validator.get_order_detail", fake_get_order_detail)
    result = validate_screenshot_against_order(
        {
            "order_id": "O202605010001",
            "payment_amount": "¥299.00",
            "product_names": ["无线蓝牙耳机 Pro"],
            "order_status": "已签收",
        },
        customer_id="C10001",
    )

    assert result["matched"] is True
    assert result["status"] == "matched"


def test_screenshot_validator_reports_amount_mismatch(monkeypatch) -> None:
    def fake_get_order_detail(order_id: str, customer_id: str | None = None) -> dict:
        return {
            "success": True,
            "order": {
                "order_id": order_id,
                "order_status": "delivered",
                "payment_amount": 2699.0,
                "items": [{"product_name": "智能扫拖机器人 X1"}],
            },
        }

    monkeypatch.setattr("agent.order_screenshot_validator.get_order_detail", fake_get_order_detail)
    result = validate_screenshot_against_order(
        {
            "order_id": "O202605010001",
            "payment_amount": "2999 元",
            "product_names": ["智能扫拖机器人 X1"],
            "order_status": "已签收",
        }
    )

    assert result["matched"] is False
    assert result["mismatches"][0]["field"] == "payment_amount"
