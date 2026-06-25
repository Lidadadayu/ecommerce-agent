from __future__ import annotations


def test_robot_tools_registered():
    from tools.tool_registry import TOOL_REGISTRY

    required = {
        "robot_vacuum_search",
        "robot_vacuum_detail",
        "robot_vacuum_compare",
        "robot_vacuum_knowledge_query",
        "robot_vacuum_diagnosis",
    }

    assert required.issubset(set(TOOL_REGISTRY.keys()))


def test_execute_robot_vacuum_search_tool():
    from tools.tool_registry import execute_tool

    result = execute_tool(
        "robot_vacuum_search",
        {
            "query": "3000以内推荐一款扫拖一体机器人",
            "budget_max": 3000,
            "need_mop": True,
        },
    )

    assert result["success"] is True
    assert result["result"]["success"] is True
    assert result["result"]["count"] > 0
