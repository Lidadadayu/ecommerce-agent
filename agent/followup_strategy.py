from __future__ import annotations

from typing import Any

from agent.constants import ticket_type_display
from agent.task_state_machine import get_task_state


SLOT_QUESTION = {
    "order_id": "请提供订单号，或者上传订单截图，我可以先识别订单信息。",
    "reason": "请简单说明售后原因，例如不想要了、包装破损、无法使用或发错货。",
    "package_status": "请确认商品是否已拆封，以及外观和附件是否完好。",
    "product_id": "这个订单可能包含多个商品，请告诉我要处理哪个商品 ID 或商品名称。",
    "ticket_type": "请确认你想办理退货、换货、维修还是退款。",
}


def pick_next_missing_slot(missing_slots: list[str], context: dict[str, Any]) -> str | None:
    if not missing_slots:
        return None
    if "order_id" in missing_slots and not context.get("order_id"):
        return "order_id"
    task = context.get("task_state") or {}
    priority = task.get("aftersale_priority") or []
    if priority and "package_status" in missing_slots and priority[0] == "return" and context.get("reason"):
        return "package_status"
    for slot in ["ticket_type", "reason", "package_status", "product_id"]:
        if slot in missing_slots:
            return slot
    return missing_slots[0]


def build_context_aware_followup(
    *,
    missing_slots: list[str],
    arguments: dict[str, Any],
    memory: Any,
    intent: str | None = None,
) -> str:
    context = getattr(memory, "current_business_context", {}) or {}
    task = get_task_state(memory)
    merged_context = dict(context)
    if task:
        merged_context["task_state"] = task.to_dict()
    merged_context.update({k: v for k, v in arguments.items() if v not in (None, "", [], {})})

    slot = pick_next_missing_slot(missing_slots, merged_context)
    if not slot:
        return "我已经拿到当前关键信息，可以继续处理。"

    prefix_parts = []
    if merged_context.get("order_id"):
        prefix_parts.append(f"我已识别到订单 {merged_context['order_id']}。")
    if arguments.get("ticket_type"):
        prefix_parts.append(f"当前先按{ticket_type_display(arguments.get('ticket_type'))}处理。")
    if task and task.aftersale_priority:
        prefix_parts.append("我会按你的目标优先判断" + "、".join(ticket_type_display(x) for x in task.aftersale_priority) + "。")

    question = SLOT_QUESTION.get(slot, f"请补充 {slot}。")
    remaining = [
        item
        for item in missing_slots
        if item != slot and not merged_context.get(item)
    ]
    remaining_text = ""
    if remaining:
        names = {
            "order_id": "订单号",
            "reason": "售后原因",
            "package_status": "是否拆封/使用",
            "product_id": "商品",
            "ticket_type": "售后类型",
        }
        remaining_text = " 后续可能还需要确认：" + "、".join(names.get(item, item) for item in remaining) + "。"
    return "".join(prefix_parts) + question + remaining_text
