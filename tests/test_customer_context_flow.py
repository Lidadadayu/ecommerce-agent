from __future__ import annotations

import sys
import types

openai_stub = types.ModuleType("openai")
openai_stub.OpenAI = object
sys.modules.setdefault("openai", openai_stub)

from agent.legacy_agent import _build_route
from agent.memory import SessionMemory
from agent.rule_router import route_user_query
from agent.slot_filling import build_effective_tool_arguments


def test_purchase_history_route() -> None:
    route = route_user_query("我买过哪些商品？")

    assert route["intent"] == "purchase_history"
    assert route["tool_name"] == "purchase_history"
    assert route["arguments"]["limit"] == 20


def test_logged_in_customer_is_injected_into_purchase_history() -> None:
    memory = SessionMemory(current_customer_id="C10002")

    route, used_memory, domain = _build_route("我买过哪些商品？", memory)

    assert domain is None
    assert used_memory is True
    assert route["intent"] == "purchase_history"
    assert route["arguments"]["customer_id"] == "C10002"


def test_logged_in_customer_is_injected_into_order_query() -> None:
    memory = SessionMemory(current_customer_id="C10001")

    route, used_memory, domain = _build_route("帮我查一下 O202605010001 这个订单", memory)

    assert domain is None
    assert used_memory is True
    assert route["intent"] == "order_query"
    assert route["arguments"]["order_id"] == "O202605010001"
    assert route["arguments"]["customer_id"] == "C10001"


def test_order_tool_effective_arguments_keep_customer_id() -> None:
    effective = build_effective_tool_arguments(
        "order_query",
        {"order_id": "O202605010001", "customer_id": "C10001"},
    )

    assert effective == {"order_id": "O202605010001", "customer_id": "C10001"}
