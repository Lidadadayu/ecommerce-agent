from __future__ import annotations

import sys
import types

openai_stub = types.ModuleType("openai")
openai_stub.OpenAI = object
sys.modules.setdefault("openai", openai_stub)

from agent.legacy_agent import _build_route, run_contextual_guarded_agent
from agent.memory import SessionMemory
from agent.rule_router import route_user_query
from agent.slot_filling import build_effective_tool_arguments


def test_aftersale_check_question_routes_to_eligibility_check() -> None:
    route = route_user_query("O202605010001 这个订单可以退货吗？")

    assert route["intent"] == "aftersale_check"
    assert route["tool_name"] == "aftersale_check"
    assert route["arguments"]["order_id"] == "O202605010001"
    assert route["arguments"]["ticket_type"] == "return"


def test_aftersale_create_request_routes_to_ticket_create() -> None:
    route = route_user_query("我要申请 O202605010001 这个订单退货，原因是耳机佩戴不合适，未拆封")

    assert route["intent"] == "ticket_create"
    assert route["tool_name"] == "ticket_create"
    assert route["arguments"]["order_id"] == "O202605010001"
    assert route["arguments"]["ticket_type"] == "return"


def test_create_ticket_missing_reason_and_package_status_does_not_call_tool() -> None:
    memory = SessionMemory()

    state = run_contextual_guarded_agent("我要申请 O202605010001 退货", memory)

    assert state["intent"] == "ticket_create"
    assert state["tool_name"] is None
    assert state["mode"] == "aftersale_slot_missing"
    assert "售后原因" in state["final_answer"]
    assert "拆封" in state["final_answer"]
    assert state["memory"]["pending_action"]["intent"] == "ticket_create"


def test_pending_aftersale_check_can_be_upgraded_to_ticket_create() -> None:
    memory = SessionMemory()

    first = run_contextual_guarded_agent("这个订单可以退货吗？", memory)
    memory = SessionMemory.from_dict(first["memory"])

    route, used_memory, domain = _build_route(
        "我要申请 O202605010001 退货，原因是耳机佩戴不合适，未拆封",
        memory,
    )

    assert domain is None
    assert used_memory is False
    assert route["intent"] == "ticket_create"
    assert route["tool_name"] == "ticket_create"
    assert route["arguments"]["order_id"] == "O202605010001"
    assert route["arguments"]["ticket_type"] == "return"


def test_ticket_create_effective_arguments_include_package_complete() -> None:
    effective = build_effective_tool_arguments(
        "ticket_create",
        {
            "order_id": "O202605010001",
            "ticket_type": "return",
            "reason": "耳机佩戴不合适",
            "package_status": "未拆封/未使用",
        },
    )

    assert effective["package_complete"] is True
