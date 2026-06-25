from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from tools.business_tools import get_order_detail


STATUS_ALIASES = {
    "delivered": ["已签收", "已收货", "已完成", "delivered", "completed"],
    "shipped": ["已发货", "运输中", "配送中", "shipped"],
    "paid": ["已支付", "待发货", "paid"],
    "cancelled": ["已取消", "已关闭", "cancelled", "closed"],
}


def _amount_to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


def _status_matches(screenshot_status: str | None, db_status: str | None) -> bool | None:
    if not screenshot_status:
        return None
    if not db_status:
        return False
    screenshot_status = str(screenshot_status).strip().lower()
    db_status = str(db_status).strip().lower()
    if screenshot_status == db_status:
        return True
    aliases = STATUS_ALIASES.get(db_status, [])
    return any(alias.lower() in screenshot_status for alias in aliases)


def _products_match(product_names: list[Any], order_items: list[dict[str, Any]]) -> bool | None:
    names = [str(x).strip().lower() for x in (product_names or []) if str(x).strip()]
    if not names:
        return None
    db_names = [str(item.get("product_name") or "").strip().lower() for item in order_items]
    for name in names:
        if any(name in db_name or db_name in name for db_name in db_names if db_name):
            return True
    return False


def validate_screenshot_against_order(
    analysis: dict[str, Any],
    *,
    customer_id: str | None = None,
) -> dict[str, Any]:
    order_id = (analysis.get("order_id") or "").strip()
    if not order_id:
        return {
            "success": False,
            "status": "missing_order_id",
            "message": "截图中未稳定识别到订单号，无法自动校验数据库订单。",
            "matched": False,
            "mismatches": [{"field": "order_id", "screenshot": None, "database": None}],
        }

    try:
        order_result = get_order_detail(order_id, customer_id=customer_id)
    except Exception as exc:
        return {
            "success": False,
            "status": "database_unavailable",
            "message": f"已识别到订单 {order_id}，但数据库暂时不可用，无法自动校验：{type(exc).__name__}: {exc}",
            "matched": False,
            "order_id": order_id,
            "mismatches": [],
        }
    if not order_result.get("success"):
        return {
            "success": False,
            "status": "order_not_found",
            "message": order_result.get("message") or f"数据库中未找到订单 {order_id}。",
            "matched": False,
            "order_id": order_id,
            "mismatches": [{"field": "order_id", "screenshot": order_id, "database": None}],
        }

    order = order_result["order"]
    checks: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    screenshot_amount = _amount_to_float(analysis.get("payment_amount"))
    db_amount = _amount_to_float(order.get("payment_amount"))
    if screenshot_amount is not None and db_amount is not None:
        ok = abs(screenshot_amount - db_amount) < 0.01
        checks.append({"field": "payment_amount", "matched": ok, "screenshot": screenshot_amount, "database": db_amount})
        if not ok:
            mismatches.append({"field": "payment_amount", "screenshot": screenshot_amount, "database": db_amount})

    status_ok = _status_matches(analysis.get("order_status"), order.get("order_status"))
    if status_ok is not None:
        checks.append({"field": "order_status", "matched": status_ok, "screenshot": analysis.get("order_status"), "database": order.get("order_status")})
        if not status_ok:
            mismatches.append({"field": "order_status", "screenshot": analysis.get("order_status"), "database": order.get("order_status")})

    products_ok = _products_match(analysis.get("product_names") or [], order.get("items") or [])
    if products_ok is not None:
        db_names = [item.get("product_name") for item in order.get("items") or []]
        checks.append({"field": "product_names", "matched": products_ok, "screenshot": analysis.get("product_names"), "database": db_names})
        if not products_ok:
            mismatches.append({"field": "product_names", "screenshot": analysis.get("product_names"), "database": db_names})

    matched = not mismatches
    if not checks:
        message = f"已根据订单号 {order_id} 查到系统订单，但截图中可比对字段不足，建议用户确认后继续。"
        status = "insufficient_fields"
    elif matched:
        message = f"系统订单记录与截图信息一致，订单 {order_id} 可继续业务处理。"
        status = "matched"
    else:
        first = mismatches[0]
        message = f"截图字段 {first['field']} 与系统订单记录不一致，请用户确认是否上传了正确订单截图。"
        status = "mismatched"

    return {
        "success": True,
        "status": status,
        "matched": matched,
        "message": message,
        "order_id": order_id,
        "order": order,
        "checks": checks,
        "mismatches": mismatches,
    }
