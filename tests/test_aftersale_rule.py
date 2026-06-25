from pprint import pprint

from tools.business_tools import (
    check_aftersale_eligibility,
    create_aftersale_ticket,
    get_tickets_by_order,
)


def main() -> None:
    print("\n=== 1. 数码配件：签收后 2 天内申请退货，应该允许 ===")
    result = check_aftersale_eligibility(
        order_id="O202605010001",
        ticket_type="return",
        reason="耳机佩戴不合适，想申请退货",
        application_time="2026-05-05 10:00:00",
    )
    pprint(result)

    print("\n=== 2. 数码配件：超过 7 天申请退货，应该拒绝 ===")
    result = check_aftersale_eligibility(
        order_id="O202605010001",
        ticket_type="return",
        reason="耳机佩戴不合适，想申请退货",
        application_time="2026-05-20 10:00:00",
    )
    pprint(result)

    print("\n=== 3. 生鲜食品：非质量问题退货，应该拒绝 ===")
    result = check_aftersale_eligibility(
        order_id="O202605030001",
        ticket_type="return",
        reason="不想要了，想申请退货",
        application_time="2026-05-04 18:00:00",
    )
    pprint(result)

    print("\n=== 4. 生鲜食品：质量问题退货，应该允许 ===")
    result = check_aftersale_eligibility(
        order_id="O202605030001",
        ticket_type="return",
        reason="收到后发现牛排包装破损，存在质量问题",
        application_time="2026-05-04 18:00:00",
    )
    pprint(result)

    print("\n=== 5. 家用电器：订单未签收申请维修，应该拒绝 ===")
    result = check_aftersale_eligibility(
        order_id="O202605020001",
        ticket_type="repair",
        reason="扫地机器人无法启动，申请维修",
        application_time="2026-05-04 10:00:00",
    )
    pprint(result)

    print("\n=== 6. 创建允许的售后工单 ===")
    result = create_aftersale_ticket(
        order_id="O202605010001",
        ticket_type="return",
        reason="耳机佩戴不合适，申请退货",
        application_time="2026-05-05 10:00:00",
    )
    pprint(result)

    print("\n=== 7. 创建不允许的售后工单，应该不会创建 ===")
    result = create_aftersale_ticket(
        order_id="O202605010001",
        ticket_type="return",
        reason="耳机佩戴不合适，申请退货",
        application_time="2026-05-20 10:00:00",
    )
    pprint(result)

    print("\n=== 8. 查询订单工单列表 ===")
    pprint(get_tickets_by_order("O202605010001"))


if __name__ == "__main__":
    main()