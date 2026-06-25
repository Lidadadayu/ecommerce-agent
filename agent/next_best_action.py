from __future__ import annotations

from datetime import datetime
from typing import Any


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def recommend_next_actions(
    *,
    intent: str | None,
    arguments: dict[str, Any],
    tool_result: dict[str, Any],
    memory: Any | None = None,
) -> list[str]:
    data = tool_result.get("result")
    data = data if isinstance(data, dict) else {}
    actions: list[str] = []

    order = data.get("order")
    if not order and isinstance(data.get("database_validation"), dict):
        order = (data.get("database_validation") or {}).get("order")
    if not order and data.get("analyses"):
        first = data["analyses"][0]
        if isinstance(first, dict):
            order = (first.get("database_validation") or {}).get("order")

    if intent == "logistics_query":
        status = data.get("current_status") or ""
        if "签收" in status or "已签收" in status:
            actions.append("订单已签收，如商品未拆封且在时效内，可以继续申请退货。")
            actions.append("如果存在质量问题，可以申请换货或维修，并上传问题照片作为凭证。")
        else:
            actions.append("可以继续查询订单详情，确认是否已发货或是否需要催发货。")

    if order:
        receive_time = _parse_datetime(order.get("receive_time"))
        if receive_time:
            elapsed_days = (datetime.now() - receive_time).days
            if elapsed_days <= 7:
                actions.append(f"该订单已签收 {elapsed_days} 天，可能仍在 7 天无理由退货期内，需确认商品是否影响二次销售。")
            if elapsed_days <= 15:
                actions.append("如果商品存在质量问题，可以继续判断是否支持换货。")
            if elapsed_days <= 30:
                actions.append("如果是家用电器或扫拖机器人故障，可以继续判断维修资格。")

    if intent == "screenshot_order_review" and data.get("success"):
        actions.append("你可以继续选择查物流、申请退货、申请换货或申请维修。")

    if intent in {"aftersale_check", "ticket_create"}:
        decision = data.get("decision") or (data.get("rule_result") or {}).get("decision")
        if decision == "approve":
            actions.append("如你确认继续，我可以帮助提交售后工单。")
        elif decision == "manual_review":
            actions.append("该申请建议进入人工审核，请保留截图、故障照片或包装照片。")
        elif data.get("eligible") is False:
            actions.append("如果退货不满足条件，可以继续尝试换货或维修规则判断。")

    deduped: list[str] = []
    for item in actions:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:3]


def append_next_best_actions(answer: str, actions: list[str]) -> str:
    if not actions:
        return answer
    lines = [answer.rstrip(), "", "下一步建议："]
    lines.extend(f"- {item}" for item in actions)
    return "\n".join(lines)
