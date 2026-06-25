from __future__ import annotations

import uuid
from typing import Any

from agent.constants import ticket_type_display
from agent.intent_slot_extractor import extract_intent_slots
from agent.rule_router import extract_ticket_type
from agent.task_state_machine import TaskState, TaskStep, get_task_state, set_task_state


def _contains_screenshot_request(text: str) -> bool:
    return any(word in text for word in ["截图", "图片", "凭证", "上传的图", "帮我看看"])


def _extract_aftersale_priority(text: str) -> list[str]:
    priority: list[str] = []
    if any(word in text for word in ["退货", "退掉", "能退", "还能不能退"]):
        priority.append("return")
    if any(word in text for word in ["换货", "换一个", "更换", "能换"]):
        priority.append("exchange")
    if any(word in text for word in ["维修", "修一下", "报修", "能修"]):
        priority.append("repair")
    if any(word in text for word in ["退款", "退钱"]):
        priority.append("refund")
    ticket_type = extract_ticket_type(text)
    if ticket_type and ticket_type not in priority:
        priority.append(ticket_type)
    return priority


def plan_user_task(user_query: str, memory: Any) -> dict[str, Any]:
    text = (user_query or "").strip()
    slots = extract_intent_slots(text, memory.to_dict() if hasattr(memory, "to_dict") else None)
    existing = get_task_state(memory)
    priority = _extract_aftersale_priority(text) or (existing.aftersale_priority if existing else [])

    complex_goal = _contains_screenshot_request(text) and bool(priority)
    if not complex_goal and existing and existing.status == "active":
        return {"created": False, "task_state": existing.to_dict(), "intent_slots": slots}

    if not complex_goal and slots.get("intent") not in {"ticket_create", "aftersale_check"}:
        return {"created": False, "task_state": existing.to_dict() if existing else None, "intent_slots": slots}

    goal_parts = []
    if _contains_screenshot_request(text):
        goal_parts.append("识别并校验订单截图")
    if priority:
        goal_parts.append("按优先级判断" + "、".join(ticket_type_display(x) for x in priority))
    goal = "，".join(goal_parts) or "完成售后任务"

    steps = []
    if _contains_screenshot_request(text):
        steps.extend(
            [
                TaskStep("识别截图订单信息", tool_name="screenshot_order_review", reason="先拿到订单号、金额、商品和状态"),
                TaskStep("数据库校验截图信息", tool_name="screenshot_order_review", reason="防止 OCR 错误导致误处理"),
            ]
        )
    steps.extend(
        [
            TaskStep("确认售后类型", reason="确定退货、换货、维修或退款"),
            TaskStep("收集关键槽位", reason="只追问当前不能推断的信息"),
            TaskStep("执行售后策略判断", tool_name="aftersale_check", reason="按订单状态、签收时间、商品政策判断"),
            TaskStep("推荐下一步动作", reason="给出退货、换货、维修或人工审核建议"),
        ]
    )

    task = TaskState(
        task_id=f"TASK{uuid.uuid4().hex[:10].upper()}",
        goal=goal,
        stage="START",
        aftersale_priority=priority,
        steps=steps,
        collected={k: v for k, v in (slots.get("arguments") or {}).items() if v not in (None, "", [], {})},
        missing_slots=list(slots.get("missing_slots") or []),
    )
    set_task_state(memory, task)
    return {"created": True, "task_state": task.to_dict(), "intent_slots": slots}


def choose_route_for_task(route: dict[str, Any], user_query: str, memory: Any) -> dict[str, Any]:
    task = get_task_state(memory)
    if not task or task.status != "active":
        return route

    if _contains_screenshot_request(user_query):
        return route

    if route.get("intent") in {"unknown", "aftersale_check", "ticket_create"} and task.aftersale_priority:
        args = dict(route.get("arguments") or {})
        args.setdefault("ticket_type", task.aftersale_priority[0])
        if task.collected.get("order_id"):
            args.setdefault("order_id", task.collected["order_id"])
        if task.collected.get("reason"):
            args.setdefault("reason", task.collected["reason"])
        intent = "aftersale_check" if "能不能" in user_query or "可以" in user_query or route.get("intent") == "aftersale_check" else route.get("intent")
        if intent not in {"aftersale_check", "ticket_create"}:
            intent = "aftersale_check"
        return {**route, "intent": intent, "tool_name": "aftersale_check" if args.get("order_id") else None, "arguments": args, "error": route.get("error")}
    return route
