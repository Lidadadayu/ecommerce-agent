from __future__ import annotations

VALID_TICKET_TYPES = {"return", "exchange", "repair", "refund", "cancel"}

TICKET_TYPE_NAME = {
    "return": "退货",
    "exchange": "换货",
    "repair": "维修",
    "refund": "退款",
    "cancel": "取消订单",
}

CATEGORY_KEYWORDS = ["扫地机器人", "扫拖一体机器人", "数码配件", "家用电器", "服饰", "生鲜食品", "虚拟商品"]

PRODUCT_KEYWORDS = [
    "蓝牙耳机", "耳机", "扫地机器人", "扫拖一体机器人", "机器人", "基站", "拖布", "尘袋", "T恤", "短袖", "牛排", "电子书", "Python",
]


def ticket_type_display(ticket_type: str | None) -> str:
    if not ticket_type:
        return "未指定"
    return TICKET_TYPE_NAME.get(ticket_type, ticket_type)
