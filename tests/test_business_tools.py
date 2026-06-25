from pprint import pprint

from tools.business_tools import (
    search_products,
    get_product_detail,
    get_order_detail,
    get_logistics,
    get_policies_by_category,
    get_tickets_by_order,
    create_aftersale_ticket,
)


def main() -> None:
    print("\n=== 1. 搜索商品 ===")
    pprint(search_products("耳机"))

    print("\n=== 2. 查询商品详情 ===")
    pprint(get_product_detail("P10001"))

    print("\n=== 3. 查询订单详情 ===")
    pprint(get_order_detail("O202605010001"))

    print("\n=== 4. 查询物流轨迹 ===")
    pprint(get_logistics("O202605010001"))

    print("\n=== 5. 查询售后政策 ===")
    pprint(get_policies_by_category("数码配件"))

    print("\n=== 6. 查询已有工单 ===")
    pprint(get_tickets_by_order("O202605010001"))

    print("\n=== 7. 创建售后工单 ===")
    pprint(
        create_aftersale_ticket(
            order_id="O202605020001",
            ticket_type="repair",
            reason="用户反馈扫地机器人无法正常启动，申请维修",
        )
    )

    print("\n=== 8. 再次查询该订单工单 ===")
    pprint(get_tickets_by_order("O202605020001"))


if __name__ == "__main__":
    main()