from __future__ import annotations


def test_search_robot_vacuum_products():
    from tools.robot_vacuum_tools import search_robot_vacuum_products

    result = search_robot_vacuum_products(
        "养宠家庭怎么选扫地机器人",
        pet_family=True,
    )

    assert result["success"] is True
    assert result["count"] > 0
    assert result["products"]
    assert any("RV" in item["product_id"] for item in result["products"])


def test_robot_vacuum_detail():
    from tools.robot_vacuum_tools import get_robot_vacuum_product_detail

    result = get_robot_vacuum_product_detail("RV4001")

    assert result["success"] is True
    assert result["product"]["product_id"] == "RV4001"
    assert "扫拖" in result["product"]["name"] or "机器人" in result["product"]["name"]


def test_robot_vacuum_compare():
    from tools.robot_vacuum_tools import compare_robot_vacuum_products

    result = compare_robot_vacuum_products(["RV2001", "RV4001"])

    assert result["success"] is True
    assert len(result["comparison"]) == 2
    assert {item["product_id"] for item in result["comparison"]} == {"RV2001", "RV4001"}
