from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.db import fetch_all


def show_products() -> None:
    rows = fetch_all("""
        SELECT product_id, product_name, category, brand, price, stock
        FROM products
        ORDER BY product_id
        LIMIT 10
    """)

    print("\n=== 商品数据 ===")
    for row in rows:
        print(row)


def show_order_detail(order_id: str) -> None:
    rows = fetch_all("""
        SELECT 
            o.order_id,
            o.order_status,
            o.payment_amount,
            o.pay_time,
            o.ship_time,
            o.receive_time,
            c.customer_name,
            p.product_id,
            p.product_name,
            p.category,
            oi.quantity,
            oi.unit_price
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        WHERE o.order_id = :order_id
    """, {"order_id": order_id})

    print(f"\n=== 订单详情：{order_id} ===")
    for row in rows:
        print(row)


def show_logistics(order_id: str) -> None:
    rows = fetch_all("""
        SELECT 
            order_id,
            carrier,
            tracking_no,
            logistics_status,
            location,
            description,
            event_time
        FROM logistics_records
        WHERE order_id = :order_id
        ORDER BY event_time
    """, {"order_id": order_id})

    print(f"\n=== 物流轨迹：{order_id} ===")
    for row in rows:
        print(row)


def show_policies(category: str) -> None:
    rows = fetch_all("""
        SELECT 
            policy_id,
            category,
            policy_type,
            title,
            allow_days,
            content
        FROM aftersale_policies
        WHERE category = :category
        ORDER BY policy_id
    """, {"category": category})

    print(f"\n=== 售后政策：{category} ===")
    for row in rows:
        print(row)


def show_tickets(order_id: str) -> None:
    rows = fetch_all("""
        SELECT 
            ticket_id,
            order_id,
            customer_id,
            product_id,
            ticket_type,
            reason,
            ticket_status,
            rule_result,
            created_at
        FROM aftersale_tickets
        WHERE order_id = :order_id
        ORDER BY created_at DESC
    """, {"order_id": order_id})

    print(f"\n=== 售后工单：{order_id} ===")
    for row in rows:
        print(row)


def main() -> None:
    show_products()
    show_order_detail("O202605010001")
    show_logistics("O202605010001")
    show_policies("数码配件")
    show_tickets("O202605010001")


if __name__ == "__main__":
    main()