from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from agent.aftersale_policy_engine import detect_quality_issue, evaluate_aftersale_policy
from agent.constants import VALID_TICKET_TYPES, ticket_type_display
from database.db import execute_write, fetch_all, fetch_one


def _customer_order_clause(customer_id: str | None) -> tuple[str, dict[str, str]]:
    if not customer_id:
        return "", {}
    return " AND o.customer_id = :customer_id", {"customer_id": customer_id.strip()}


def search_products(keyword: str, limit: int = 10) -> dict:
    keyword = keyword.strip()
    limit = max(1, min(limit, 50))
    if not keyword:
        return {"success": False, "message": "搜索关键词不能为空", "count": 0, "products": []}
    rows = fetch_all("""
        SELECT product_id, product_name, category, brand, price, stock, status
        FROM products
        WHERE product_name ILIKE :keyword OR category ILIKE :keyword OR brand ILIKE :keyword
        ORDER BY product_id
        LIMIT :limit
    """, {"keyword": f"%{keyword}%", "limit": limit})
    return {"success": True, "message": f"共找到 {len(rows)} 个相关商品", "count": len(rows), "products": rows}


def get_product_detail(product_id: str) -> dict:
    row = fetch_one("""
        SELECT product_id, product_name, category, brand, price, stock, specs, status, created_at
        FROM products
        WHERE product_id = :product_id
    """, {"product_id": product_id.strip()})
    if not row:
        return {"success": False, "message": f"未找到商品：{product_id}", "product": None}
    return {"success": True, "message": "商品详情查询成功", "product": row}


def get_order_detail(order_id: str, customer_id: str | None = None) -> dict:
    order_id = order_id.strip()
    customer_filter, customer_params = _customer_order_clause(customer_id)
    rows = fetch_all("""
        SELECT o.order_id, o.customer_id, c.customer_name, c.phone_masked, c.level AS customer_level,
               o.order_status, o.payment_amount, o.pay_time, o.ship_time, o.receive_time, o.created_at,
               p.product_id, p.product_name, p.category, p.brand, oi.quantity, oi.unit_price
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        WHERE o.order_id = :order_id
        """ + customer_filter + """
        ORDER BY oi.item_id
    """, {"order_id": order_id, **customer_params})
    if not rows:
        if customer_id:
            return {"success": False, "message": f"当前用户 {customer_id} 下未找到订单：{order_id}", "order": None}
        return {"success": False, "message": f"未找到订单：{order_id}", "order": None}
    first = rows[0]
    order = {k: first[k] for k in ["order_id", "customer_id", "customer_name", "phone_masked", "customer_level", "order_status", "payment_amount", "pay_time", "ship_time", "receive_time", "created_at"]}
    order["items"] = [{"product_id": r["product_id"], "product_name": r["product_name"], "category": r["category"], "brand": r["brand"], "quantity": r["quantity"], "unit_price": r["unit_price"]} for r in rows]
    return {"success": True, "message": "订单详情查询成功", "order": order}


def get_logistics(order_id: str, customer_id: str | None = None) -> dict:
    order_id = order_id.strip()
    if customer_id:
        order_result = get_order_detail(order_id, customer_id=customer_id)
        if not order_result["success"]:
            return {"success": False, "message": order_result["message"], "count": 0, "logistics": []}
    rows = fetch_all("""
        SELECT order_id, carrier, tracking_no, logistics_status, location, description, event_time
        FROM logistics_records
        WHERE order_id = :order_id
        ORDER BY event_time
    """, {"order_id": order_id})
    if not rows:
        return {"success": False, "message": f"未找到订单 {order_id} 的物流记录", "count": 0, "logistics": []}
    latest = rows[-1]
    return {"success": True, "message": f"物流查询成功，当前状态：{latest['logistics_status']}", "count": len(rows), "current_status": latest["logistics_status"], "latest_location": latest["location"], "latest_event_time": latest["event_time"], "logistics": rows}


def get_policies_by_category(category: str) -> dict:
    rows = fetch_all("""
        SELECT policy_id, category, policy_type, title, content, allow_days, conditions, created_at
        FROM aftersale_policies
        WHERE category = :category
        ORDER BY policy_id
    """, {"category": category.strip()})
    if not rows:
        return {"success": False, "message": f"未找到类别 {category} 的售后政策", "count": 0, "policies": []}
    return {"success": True, "message": f"共找到 {len(rows)} 条售后政策", "count": len(rows), "policies": rows}


def get_tickets_by_order(order_id: str, customer_id: str | None = None) -> dict:
    if customer_id:
        order_result = get_order_detail(order_id, customer_id=customer_id)
        if not order_result["success"]:
            return {"success": False, "message": order_result["message"], "count": 0, "tickets": []}
    rows = fetch_all("""
        SELECT ticket_id, order_id, customer_id, product_id, ticket_type, reason, ticket_status, rule_result, created_at, updated_at
        FROM aftersale_tickets
        WHERE order_id = :order_id
        ORDER BY created_at DESC
    """, {"order_id": order_id.strip()})
    return {"success": True, "message": f"共找到 {len(rows)} 个售后工单", "count": len(rows), "tickets": rows}


def create_aftersale_ticket(order_id: str, ticket_type: str, reason: str, product_id: str | None = None, application_time: str | datetime | None = None, package_complete: bool = True, force_create: bool = False, customer_id: str | None = None, evidence_ids: list[str] | None = None) -> dict:
    eligibility = check_aftersale_eligibility(order_id, ticket_type, reason, product_id, application_time, package_complete, customer_id=customer_id)
    if not eligibility["success"]:
        return {"success": False, "message": eligibility["message"], "eligibility": eligibility, "ticket": None}
    if not eligibility["eligible"] and not force_create:
        return {"success": False, "message": f"不满足售后条件，未创建工单：{eligibility['message']}", "eligibility": eligibility, "ticket": None}
    order_result = get_order_detail(order_id, customer_id=customer_id)
    if not order_result["success"]:
        return {"success": False, "message": order_result["message"], "eligibility": eligibility, "ticket": None}
    order = order_result["order"]
    rule_result = eligibility["rule_result"]
    evidence_ids = [str(x) for x in (evidence_ids or []) if x]
    if evidence_ids:
        rule_result["evidence_ids"] = evidence_ids
        rule_result["evidence_note"] = "用户已上传订单截图等售后凭证，供人工客服审核参考。"

    product_id = product_id or rule_result["product_id"]
    ticket_id = f"T{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
    execute_write("""
        INSERT INTO aftersale_tickets (ticket_id, order_id, customer_id, product_id, ticket_type, reason, ticket_status, rule_result, created_at, updated_at)
        VALUES (:ticket_id, :order_id, :customer_id, :product_id, :ticket_type, :reason, :ticket_status, CAST(:rule_result AS jsonb), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, {"ticket_id": ticket_id, "order_id": order_id, "customer_id": order["customer_id"], "product_id": product_id, "ticket_type": ticket_type, "reason": reason, "ticket_status": "created", "rule_result": json.dumps(rule_result, ensure_ascii=False)})
    ticket = fetch_one("SELECT ticket_id, order_id, customer_id, product_id, ticket_type, reason, ticket_status, rule_result, created_at, updated_at FROM aftersale_tickets WHERE ticket_id = :ticket_id", {"ticket_id": ticket_id})
    return {
        "success": True,
        "message": "售后工单创建成功",
        "eligibility": eligibility,
        "ticket": ticket,
        "evidence_ids": evidence_ids,
    }


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _detect_quality_issue(reason: str) -> bool:
    return detect_quality_issue(reason)


def check_aftersale_eligibility(order_id: str, ticket_type: str, reason: str, product_id: str | None = None, application_time: str | datetime | None = None, package_complete: bool = True, has_quality_issue: bool | None = None, customer_id: str | None = None) -> dict:
    if ticket_type not in VALID_TICKET_TYPES:
        return {"success": False, "eligible": False, "message": f"不支持的售后类型：{ticket_type}", "rule_result": {"eligible": False, "reason": "售后类型不合法", "ticket_type": ticket_type}}
    order_result = get_order_detail(order_id, customer_id=customer_id)
    if not order_result["success"]:
        return {"success": False, "eligible": False, "message": order_result["message"], "rule_result": {"eligible": False, "reason": "订单不存在"}}
    order = order_result["order"]
    items = order["items"]
    if product_id is None:
        if len(items) == 1:
            product_id = items[0]["product_id"]
        else:
            return {"success": False, "eligible": False, "message": "该订单包含多个商品，请指定 product_id", "rule_result": {"eligible": False, "reason": "订单包含多个商品，无法确定售后商品", "order_id": order_id, "ticket_type": ticket_type}}
    item = next((x for x in items if x["product_id"] == product_id), None)
    if item is None:
        return {"success": False, "eligible": False, "message": f"商品 {product_id} 不属于订单 {order_id}", "rule_result": {"eligible": False, "reason": "商品不属于该订单", "order_id": order_id, "product_id": product_id, "ticket_type": ticket_type}}

    category = item["category"]
    receive_time = _to_datetime(order["receive_time"])
    application_dt = datetime.now() if application_time is None else _to_datetime(application_time)
    if application_dt is None:
        return {"success": False, "eligible": False, "message": "application_time 格式错误", "rule_result": {"eligible": False, "reason": "申请时间格式错误", "order_id": order_id, "product_id": product_id, "ticket_type": ticket_type}}
    has_quality_issue = _detect_quality_issue(reason) if has_quality_issue is None else has_quality_issue
    policies_result = get_policies_by_category(category)
    if not policies_result["success"]:
        return {"success": True, "eligible": False, "message": f"未找到 {category} 类目的售后政策", "rule_result": {"eligible": False, "order_id": order_id, "product_id": product_id, "category": category, "ticket_type": ticket_type, "reason": "未找到对应类目的售后政策"}}
    policy = next((p for p in policies_result["policies"] if p["policy_type"] == ticket_type), None)
    if policy is None:
        return {"success": True, "eligible": False, "message": f"{category} 类目不支持{ticket_type_display(ticket_type)}类型售后", "rule_result": {"eligible": False, "order_id": order_id, "product_id": product_id, "category": category, "ticket_type": ticket_type, "reason": "未找到对应售后类型的政策", "available_policy_types": [p["policy_type"] for p in policies_result["policies"]]}}
    if receive_time is None:
        return {"success": True, "eligible": False, "message": "订单没有签收时间，无法判断售后期限", "rule_result": {"eligible": False, "order_id": order_id, "product_id": product_id, "category": category, "ticket_type": ticket_type, "policy_title": policy["title"], "reason": "缺少签收时间"}}
    decision = evaluate_aftersale_policy(
        order=order,
        item=item,
        policy=policy,
        ticket_type=ticket_type,
        reason=reason,
        receive_time=receive_time,
        application_time=application_dt,
        package_complete=package_complete,
        has_quality_issue=has_quality_issue,
    )
    payload = decision.to_dict()
    rule_result = payload["rule_result"]
    rule_result.setdefault("decision", payload["decision"])
    rule_result.setdefault("matched_rules", payload["matched_rules"])

    if decision.eligible:
        message = "符合售后申请条件" if decision.decision == "approve" else decision.reason
    elif decision.reason == "订单未签收或未完成，不满足售后申请条件":
        message = "订单尚未签收，暂不能申请该类型售后"
    elif decision.reason == "该商品类别不支持无理由售后":
        message = "该类商品不支持无理由售后，需要存在质量问题"
    elif decision.reason == "政策要求存在质量问题，但申请原因未体现质量问题":
        message = "该售后类型需要存在质量问题"
    elif decision.reason == "包装或配件不完整":
        message = "商品包装或配件不完整，不满足无理由退货条件"
    elif decision.reason == "超过售后允许期限":
        message = f"已超过 {policy.get('allow_days')} 天售后期限"
    else:
        message = decision.reason

    return {
        "success": True,
        "eligible": decision.eligible,
        "message": message,
        "decision": decision.decision,
        "reason": decision.reason,
        "matched_rules": decision.matched_rules,
        "rule_result": rule_result,
    }


# =========================
# Stage 3 extended tools
# =========================

def get_recent_orders(customer_id: str | None = None, limit: int = 5) -> dict:
    """查询最近订单。未提供 customer_id 时返回系统最近订单，适合模拟系统演示。"""
    limit = max(1, min(int(limit or 5), 20))
    if customer_id:
        rows = fetch_all("""
            SELECT o.order_id, o.customer_id, c.customer_name, c.level AS customer_level,
                   o.order_status, o.payment_amount, o.created_at, o.pay_time,
                   o.ship_time, o.receive_time, COUNT(oi.item_id) AS item_count
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            LEFT JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.customer_id = :customer_id
            GROUP BY o.order_id, o.customer_id, c.customer_name, c.level,
                     o.order_status, o.payment_amount, o.created_at,
                     o.pay_time, o.ship_time, o.receive_time
            ORDER BY o.created_at DESC
            LIMIT :limit
        """, {"customer_id": customer_id, "limit": limit})
    else:
        rows = fetch_all("""
            SELECT o.order_id, o.customer_id, c.customer_name, c.level AS customer_level,
                   o.order_status, o.payment_amount, o.created_at, o.pay_time,
                   o.ship_time, o.receive_time, COUNT(oi.item_id) AS item_count
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            LEFT JOIN order_items oi ON o.order_id = oi.order_id
            GROUP BY o.order_id, o.customer_id, c.customer_name, c.level,
                     o.order_status, o.payment_amount, o.created_at,
                     o.pay_time, o.ship_time, o.receive_time
            ORDER BY o.created_at DESC
            LIMIT :limit
        """, {"limit": limit})
    return {"success": True, "message": f"共找到 {len(rows)} 个最近订单", "count": len(rows), "orders": rows}


def get_customer_purchases(customer_id: str, limit: int = 20) -> dict:
    customer_id = customer_id.strip()
    limit = max(1, min(int(limit or 20), 50))
    customer = fetch_one(
        "SELECT customer_id, customer_name, phone_masked, level FROM customers WHERE customer_id = :customer_id",
        {"customer_id": customer_id},
    )
    if not customer:
        return {"success": False, "message": f"未找到用户：{customer_id}", "customer": None, "count": 0, "purchases": []}

    rows = fetch_all("""
        SELECT o.order_id, o.customer_id, o.order_status, o.payment_amount,
               o.pay_time, o.ship_time, o.receive_time, o.created_at,
               p.product_id, p.product_name, p.category, p.brand,
               oi.quantity, oi.unit_price
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        WHERE o.customer_id = :customer_id
        ORDER BY o.created_at DESC, oi.item_id
        LIMIT :limit
    """, {"customer_id": customer_id, "limit": limit})

    return {
        "success": True,
        "message": f"用户 {customer_id} 共查询到 {len(rows)} 条购买商品记录",
        "customer": customer,
        "count": len(rows),
        "purchases": rows,
    }


def find_customer_purchase(customer_id: str, product_id: str | None = None, product_name: str | None = None) -> dict:
    customer_id = customer_id.strip()
    params: dict[str, Any] = {"customer_id": customer_id}
    filters = ["o.customer_id = :customer_id"]

    if product_id:
        filters.append("p.product_id = :product_id")
        params["product_id"] = product_id.strip()
    if product_name:
        filters.append("(p.product_name ILIKE :product_name OR p.category ILIKE :product_name)")
        params["product_name"] = f"%{product_name.strip()}%"

    if len(filters) == 1:
        return {"success": False, "message": "请提供商品 ID 或商品名称用于匹配购买记录", "purchase": None}

    rows = fetch_all(f"""
        SELECT o.order_id, o.customer_id, o.order_status, o.payment_amount,
               o.pay_time, o.ship_time, o.receive_time, o.created_at,
               p.product_id, p.product_name, p.category, p.brand,
               oi.quantity, oi.unit_price
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        WHERE {' AND '.join(filters)}
        ORDER BY o.created_at DESC, oi.item_id
        LIMIT 5
    """, params)

    if not rows:
        target = product_id or product_name
        return {"success": False, "message": f"当前用户 {customer_id} 未查询到购买过该商品：{target}", "purchase": None}

    return {
        "success": True,
        "message": f"已匹配到用户 {customer_id} 的购买记录",
        "purchase": rows[0],
        "candidates": rows,
    }


def cancel_order(order_id: str, reason: str = "用户申请取消订单", customer_id: str | None = None) -> dict:
    """取消未发货/未签收类状态订单；已发货或已完成订单提示转人工。"""
    order_result = get_order_detail(order_id, customer_id=customer_id)
    if not order_result.get("success"):
        return {"success": False, "message": order_result.get("message"), "order": None}
    order = order_result["order"]
    old_status = order.get("order_status")
    if old_status in {"shipped", "delivered", "completed", "cancelled", "closed"}:
        return {"success": False, "message": f"当前订单状态为 {old_status}，暂不支持自动取消，建议转人工客服处理。", "order_id": order_id, "old_status": old_status, "new_status": old_status, "reason": reason}
    execute_write("""
        UPDATE orders
        SET order_status = 'cancelled'
        WHERE order_id = :order_id
    """, {"order_id": order_id})
    return {"success": True, "message": "订单取消申请已处理，订单状态已更新为 cancelled。", "order_id": order_id, "old_status": old_status, "new_status": "cancelled", "reason": reason}


def urge_shipment(order_id: str, reason: str = "用户催发货", customer_id: str | None = None) -> dict:
    """催发货。当前不新增数据库表，只根据订单状态返回处理建议。"""
    order_result = get_order_detail(order_id, customer_id=customer_id)
    if not order_result.get("success"):
        return {"success": False, "message": order_result.get("message"), "order_id": order_id}
    order = order_result["order"]
    status = order.get("order_status")
    if status in {"shipped", "delivered", "completed"}:
        return {"success": True, "message": "该订单已发货或已签收，无需催发货。", "order_id": order_id, "order_status": status, "ship_time": order.get("ship_time"), "receive_time": order.get("receive_time")}
    if status in {"cancelled", "closed"}:
        return {"success": False, "message": "该订单已取消或已关闭，不能催发货。", "order_id": order_id, "order_status": status}
    return {"success": True, "message": "已记录催发货需求，建议客服核实仓库处理进度。", "order_id": order_id, "order_status": status, "reason": reason, "customer_name": order.get("customer_name"), "payment_amount": order.get("payment_amount")}


def get_refund_progress(order_id: str, customer_id: str | None = None) -> dict:
    """查询退款/退货相关售后进度，并校验订单归属。"""
    order_id = order_id.strip()

    if customer_id:
        order_result = get_order_detail(order_id, customer_id=customer_id)
        if not order_result["success"]:
            return {
                "success": False,
                "message": order_result["message"],
                "order_id": order_id,
                "tickets": [],
            }

    rows = fetch_all("""
        SELECT ticket_id, order_id, customer_id, product_id, ticket_type, reason,
               ticket_status, created_at, updated_at
        FROM aftersale_tickets
        WHERE order_id = :order_id
          AND ticket_type IN ('return', 'refund')
        ORDER BY created_at DESC
    """, {"order_id": order_id})

    if customer_id:
        rows = [row for row in rows if str(row.get("customer_id")) == str(customer_id)]

    if not rows:
        return {
            "success": False,
            "message": f"订单 {order_id} 暂未查询到退货或退款相关工单。",
            "order_id": order_id,
            "tickets": [],
        }

    status_text = {
        "created": "工单已创建，等待平台处理",
        "pending_review": "等待人工客服审核",
        "processing": "正在处理中",
        "approved": "审核通过，等待后续退款或退货流程",
        "rejected": "审核未通过",
        "completed": "处理完成",
        "closed": "工单已关闭",
    }
    tickets = []
    for row in rows:
        tickets.append({
            **row,
            "ticket_type_name": ticket_type_display(row.get("ticket_type")),
            "progress_text": status_text.get(row.get("ticket_status"), "当前状态待客服确认"),
        })

    return {
        "success": True,
        "message": f"共查询到 {len(tickets)} 个退款/退货相关工单。",
        "order_id": order_id,
        "tickets": tickets,
    }


def get_operation_metrics(days: int = 30) -> dict:
    """查询基础运营指标：订单量、GMV、售后工单量、退款相关工单率等。"""
    days = max(1, min(int(days or 30), 365))
    interval_text = f"{days} days"
    order_metrics = fetch_one("""
        SELECT COUNT(*) AS order_count, COALESCE(SUM(payment_amount), 0) AS gmv
        FROM orders
        WHERE created_at >= CURRENT_TIMESTAMP - CAST(:interval_text AS interval)
    """, {"interval_text": interval_text}) or {}
    ticket_metrics = fetch_one("""
        SELECT COUNT(*) AS ticket_count,
               COUNT(*) FILTER (WHERE ticket_type IN ('return', 'refund')) AS refund_related_count,
               COUNT(*) FILTER (WHERE ticket_status = 'pending_review') AS pending_review_count
        FROM aftersale_tickets
        WHERE created_at >= CURRENT_TIMESTAMP - CAST(:interval_text AS interval)
    """, {"interval_text": interval_text}) or {}
    status_rows = fetch_all("""
        SELECT order_status, COUNT(*) AS count
        FROM orders
        WHERE created_at >= CURRENT_TIMESTAMP - CAST(:interval_text AS interval)
        GROUP BY order_status
        ORDER BY count DESC
    """, {"interval_text": interval_text})
    order_count = int(order_metrics.get("order_count") or 0)
    refund_related_count = int(ticket_metrics.get("refund_related_count") or 0)
    refund_ticket_rate = round(refund_related_count / order_count, 4) if order_count else 0.0
    return {"success": True, "message": f"已生成近 {days} 天基础运营指标。", "days": days, "order_count": order_count, "gmv": order_metrics.get("gmv") or 0, "ticket_count": int(ticket_metrics.get("ticket_count") or 0), "refund_related_count": refund_related_count, "pending_review_count": int(ticket_metrics.get("pending_review_count") or 0), "refund_ticket_rate": refund_ticket_rate, "order_status_distribution": status_rows}
