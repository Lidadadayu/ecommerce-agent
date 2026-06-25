from __future__ import annotations

from typing import Any

from agent.memory import SessionMemory
from agent.rule_router import route_user_query
from agent.slot_filling import merge_aftersale_slots, missing_aftersale_slots


INTENT_TO_AFTERSALE_TYPE = {
    "ticket_create": "after_sale",
    "aftersale_check": "after_sale_check",
}


def _normalize_reason(user_query: str, reason: Any) -> str | None:
    if reason:
        return str(reason)
    if any(word in user_query for word in ["包装破了", "包装破损", "外包装破", "盒子破了", "包裹破了"]):
        return "包装破损"
    if any(word in user_query for word in ["坏了", "不能用", "无法使用", "故障"]):
        return "商品故障"
    return None


def extract_intent_slots(user_query: str, memory: dict[str, Any] | SessionMemory | None = None) -> dict[str, Any]:
    memory_obj = memory if isinstance(memory, SessionMemory) else SessionMemory.from_dict(memory if isinstance(memory, dict) else None)
    route = route_user_query(user_query)
    intent = route.get("intent") or "unknown"
    arguments = dict(route.get("arguments") or {})

    if intent in {"ticket_create", "aftersale_check"}:
        arguments = merge_aftersale_slots(arguments, user_query, memory_obj, use_current_order=True)
        normalized_reason = _normalize_reason(user_query, arguments.get("reason"))
        if normalized_reason:
            arguments["reason"] = normalized_reason
        missing = missing_aftersale_slots(arguments, intent)
    else:
        missing = []
        if intent in {"order_query", "logistics_query", "ticket_query", "refund_progress", "order_cancel", "shipment_urge"} and not arguments.get("order_id"):
            missing.append("order_id")

    after_sale_type = arguments.get("ticket_type")
    return {
        "intent": intent,
        "tool_name": route.get("tool_name"),
        "order_id": arguments.get("order_id"),
        "product_id": arguments.get("product_id"),
        "product_name": arguments.get("product_name"),
        "reason": arguments.get("reason"),
        "after_sale_type": after_sale_type,
        "need_slot_filling": bool(missing or route.get("error")),
        "missing_slots": missing,
        "arguments": arguments,
        "confidence": "high" if intent != "unknown" else "low",
        "source": "rules_with_slot_merge",
    }
