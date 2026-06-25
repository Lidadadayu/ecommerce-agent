from __future__ import annotations

from agent.memory import SessionMemory
from agent.legacy_agent import _build_route
from agent.rule_router import route_user_query
from agent.task_planner import choose_route_for_task, plan_user_task


def test_planner_creates_multistep_task_for_screenshot_return_exchange() -> None:
    memory = SessionMemory()
    plan = plan_user_task("这个订单截图你帮我看看，我想知道还能不能退，不行的话看看能不能换。", memory)

    task = plan["task_state"]
    assert plan["created"] is True
    assert task["stage"] == "START"
    assert task["aftersale_priority"] == ["return", "exchange"]
    assert any(step["tool_name"] == "screenshot_order_review" for step in task["steps"])
    assert memory.current_business_context["task_state"]["goal"]


def test_planner_prefers_current_task_aftersale_type() -> None:
    memory = SessionMemory()
    plan_user_task("这个订单截图你帮我看看，我想知道还能不能退，不行的话看看能不能换。", memory)
    route = {"intent": "unknown", "tool_name": None, "arguments": {}, "error": None}

    planned = choose_route_for_task(route, "继续处理", memory)

    assert planned["intent"] == "aftersale_check"
    assert planned["arguments"]["ticket_type"] == "return"


def test_complex_screenshot_aftersale_request_routes_to_screenshot_review() -> None:
    query = "这个订单截图你帮我看看，我想知道还能不能退，不行的话看看能不能换。"
    route = route_user_query(query)

    assert route["intent"] == "screenshot_order_review"

    memory = SessionMemory()
    planned_route, used_memory, domain = _build_route(query, memory)

    assert domain is None
    assert planned_route["intent"] == "screenshot_order_review"
    assert memory.current_business_context["task_state"]["aftersale_priority"] == ["return", "exchange"]
