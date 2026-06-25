from __future__ import annotations


def test_robot_vacuum_presales_route():
    from agent.rule_router import route_user_query

    route = route_user_query("养宠家庭怎么选扫地机器人")

    assert route["intent"] == "robot_vacuum_search"
    assert route["tool_name"] == "robot_vacuum_search"
    assert route["arguments"]["pet_family"] is True


def test_robot_vacuum_fault_route():
    from agent.rule_router import route_user_query

    route = route_user_query("扫地机器人不回充怎么办")

    assert route["intent"] == "robot_vacuum_diagnosis"
    assert route["tool_name"] == "robot_vacuum_diagnosis"
    assert route["arguments"]["query"] == "扫地机器人不回充怎么办"


def test_robot_vacuum_compare_route():
    from agent.rule_router import route_user_query

    route = route_user_query("对比 RV2001 和 RV4001")

    assert route["intent"] == "robot_vacuum_compare"
    assert route["tool_name"] == "robot_vacuum_compare"
    assert route["arguments"]["product_ids"] == ["RV2001", "RV4001"]


def test_robot_vacuum_detail_route():
    from agent.rule_router import route_user_query

    route = route_user_query("RV4001 参数怎么样")

    assert route["intent"] == "robot_vacuum_detail"
    assert route["tool_name"] == "robot_vacuum_detail"
    assert route["arguments"]["product_id"] == "RV4001"
