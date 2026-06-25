from __future__ import annotations

import re
from typing import Any

from agent.constants import ticket_type_display
from agent.memory import SessionMemory
from agent.patterns import extract_order_id, extract_product_id


GENERIC_AFTERSALE_REASONS = {
    "我要退货", "我想退货", "需要退货", "帮我退货", "办理退货", "给我退货", "我要申请退货", "申请退货",
    "我要换货", "我想换货", "需要换货", "我要维修", "我想维修", "需要维修", "我要退款", "我想退款", "需要退款",
}

CHECK_QUESTION_WORDS = [
    "可以吗", "行吗", "能不能", "能否", "是否可以", "可不可以", "可以退", "可以换", "可以维修", "可以退款",
    "能退", "能换", "能修", "能退款", "支持退", "支持换", "支持维修", "支持退款", "这个订单可以", "这个商品可以",
]

REASON_KEYWORDS = [
    "不想要", "不需要", "买错", "拍错", "质量问题", "有质量问题", "坏了", "损坏", "破损", "无法使用",
    "不能使用", "不能开机", "无法开机", "发错货", "发错", "漏发", "少发", "尺寸不合适", "颜色不对",
    "不喜欢", "描述不符", "假货", "异味", "佩戴不合适", "不回充", "不出水", "雷达异常", "建图失败",
]


def clean_slot_text(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[。！？!?，,；;：:\s]+$", "", value)
    return value.strip()


def is_check_question_text(text: str | None) -> bool:
    if not text:
        return False
    normalized = clean_slot_text(text)
    if any(word in normalized for word in CHECK_QUESTION_WORDS):
        return True
    return normalized.endswith(("吗", "么", "？", "?"))


def is_generic_reason(text: str | None) -> bool:
    if not text:
        return True
    normalized = clean_slot_text(text)
    if is_check_question_text(normalized):
        return True
    if normalized in GENERIC_AFTERSALE_REASONS:
        return True

    normalized_without_ids = re.sub(r"\bO\d{12}\b", "", normalized)
    normalized_without_ids = re.sub(r"\bP\d{5,}\b", "", normalized_without_ids)
    generic_candidate = normalized_without_ids
    for word in [
        "这个订单",
        "该订单",
        "订单",
        "这个商品",
        "该商品",
        "商品",
        "我要申请",
        "我想申请",
        "帮我申请",
        "帮我",
        "我要",
        "我想",
        "需要",
        "办理",
        "提交",
        "申请",
        "售后",
    ]:
        generic_candidate = generic_candidate.replace(word, "")
    generic_candidate = clean_slot_text(generic_candidate)
    if generic_candidate in {"退货", "换货", "维修", "退款", "退换货"}:
        return True
    if len(generic_candidate) <= 8 and any(word in generic_candidate for word in ["退货", "换货", "维修", "退款"]):
        return True

    if len(normalized) <= 8 and any(word in normalized for word in ["退货", "换货", "维修", "退款"]):
        return True
    return False


def extract_product_name(text: str) -> str | None:
    patterns = [
        r"商品(?:名称)?是(.+)", r"商品(?:名称)?为(.+)", r"买的是(.+)", r"买了(.+)",
        r"退的是(.+)", r"换的是(.+)", r"维修的是(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = clean_slot_text(match.group(1))
            if value and len(value) <= 40:
                return value

    if (
        len(text.strip()) <= 20
        and not extract_order_id(text)
        and not extract_reason(text)
        and not extract_package_status(text)
        and any(word in text for word in ["手机", "耳机", "机器人", "扫地机器人", "电脑", "衣服", "鞋", "牛排", "电子书"])
    ):
        return clean_slot_text(text)

    return None


def extract_reason(text: str) -> str | None:
    if is_check_question_text(text):
        return None

    patterns = [
        r"原因是(.+)", r"原因为(.+)", r"退货原因是(.+)", r"换货原因是(.+)",
        r"维修原因是(.+)", r"退款原因是(.+)", r"因为(.+)", r"由于(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = clean_slot_text(match.group(1))
            if value and not is_check_question_text(value):
                return value

    for keyword in REASON_KEYWORDS:
        if keyword in text:
            return keyword

    return None


def extract_package_status(text: str) -> str | None:
    unopened_words = ["未拆封", "没拆封", "没有拆封", "未打开", "没打开", "没有打开", "未使用", "没使用", "没有使用", "全新"]
    opened_words = ["已经拆封", "已拆封", "拆封了", "拆开了", "打开了", "已经打开", "已经使用", "使用过", "用过", "试用过", "已经用了", "用了"]

    if any(word in text for word in unopened_words):
        return "未拆封/未使用"
    if any(word in text for word in opened_words):
        return "已拆封/已使用"
    return None


def merge_aftersale_slots(
    base_arguments: dict[str, Any],
    user_query: str,
    memory: SessionMemory,
    *,
    use_current_order: bool = True,
) -> dict[str, Any]:
    arguments = dict(base_arguments or {})

    order_id = arguments.get("order_id") or extract_order_id(user_query)
    if not order_id and use_current_order:
        order_id = memory.current_order_id
    if order_id:
        arguments["order_id"] = order_id

    ticket_type = arguments.get("ticket_type")
    if ticket_type:
        arguments["ticket_type"] = ticket_type

    product_id = arguments.get("product_id") or extract_product_id(user_query) or memory.current_product_id
    if product_id:
        arguments["product_id"] = product_id

    product_name = arguments.get("product_name") or extract_product_name(user_query)
    if product_name:
        arguments["product_name"] = product_name

    extracted_reason = extract_reason(user_query)
    existing_reason = arguments.get("reason")

    if extracted_reason:
        arguments["reason"] = extracted_reason
    elif existing_reason and not is_generic_reason(existing_reason):
        arguments["reason"] = existing_reason
    elif existing_reason:
        arguments["raw_reason"] = existing_reason
        arguments.pop("reason", None)

    package_status = arguments.get("package_status") or extract_package_status(user_query)
    if package_status:
        arguments["package_status"] = package_status

    return arguments


def missing_aftersale_slots(arguments: dict[str, Any], intent: str) -> list[str]:
    missing: list[str] = []

    if not arguments.get("ticket_type"):
        missing.append("ticket_type")
    if not arguments.get("order_id"):
        missing.append("order_id")

    if intent == "ticket_create":
        if is_generic_reason(arguments.get("reason")):
            missing.append("reason")
        if not arguments.get("package_status"):
            missing.append("package_status")

    return missing


def slot_display_name(slot: str) -> str:
    mapping = {
        "ticket_type": "售后类型，例如退货、换货、维修或退款",
        "order_id": "订单号，例如 O202605010001",
        "reason": "售后原因，例如不想要了、质量问题、发错货等",
        "package_status": "商品是否已拆封或使用",
        "product_id": "商品 ID，例如 P10001",
        "product_name": "商品名称或商品 ID",
    }
    return mapping.get(slot, slot)


def build_aftersale_slot_reply(
    arguments: dict[str, Any],
    missing_slots: list[str],
    intent: str | None = None,
) -> str:
    recorded_parts: list[str] = []

    if arguments.get("ticket_type"):
        recorded_parts.append(f"售后类型：{ticket_type_display(arguments['ticket_type'])}")
    if arguments.get("order_id"):
        recorded_parts.append(f"订单号：{arguments['order_id']}")
    if arguments.get("product_id"):
        recorded_parts.append(f"商品 ID：{arguments['product_id']}")
    if arguments.get("product_name"):
        recorded_parts.append(f"商品名称：{arguments['product_name']}")
    if arguments.get("reason") and not is_generic_reason(arguments.get("reason")):
        recorded_parts.append(f"原因：{arguments['reason']}")
    if arguments.get("package_status"):
        recorded_parts.append(f"拆封/使用状态：{arguments['package_status']}")

    if intent == "aftersale_check":
        action_text = "判断售后资格"
    elif intent == "ticket_create":
        action_text = "处理售后申请"
    else:
        action_text = "继续处理"

    lines: list[str] = []

    if recorded_parts:
        lines.append("好的，我已记录以下信息：")
        for item in recorded_parts:
            lines.append(f"- {item}")
        lines.append("")
    else:
        lines.append("好的，我可以继续帮你处理售后问题。")
        lines.append("")

    lines.append(f"为了继续{action_text}，还需要补充：")
    for index, slot in enumerate(missing_slots, start=1):
        lines.append(f"{index}. {slot_display_name(slot)}")

    lines.append("")
    if intent == "aftersale_check":
        lines.append("补充订单号后，我会先帮你做售后资格预判断。")
    else:
        lines.append("补充完整后，我会继续帮你进行售后资格预判断，并在需要时生成售后工单。")

    return "\n".join(lines)


def build_effective_tool_arguments(intent: str, arguments: dict[str, Any]) -> dict[str, Any]:
    allowed_by_intent = {
        "order_query": {"order_id", "customer_id"},
        "recent_orders": {"customer_id", "limit"},
        "purchase_history": {"customer_id", "limit"},
        "order_cancel": {"order_id", "reason", "customer_id"},
        "shipment_urge": {"order_id", "reason", "customer_id"},
        "refund_progress": {"order_id", "customer_id"},
        "operation_metrics": {"days"},
        "logistics_query": {"order_id", "customer_id"},
        "ticket_query": {"order_id", "customer_id"},
        "product_detail": {"product_id"},
        "product_search": {"keyword", "limit"},
        "policy_query": {"category"},
        "robot_vacuum_search": {"query", "budget_max", "need_mop", "need_auto_dust", "need_auto_mop_wash", "pet_family", "area_min"},
        "robot_vacuum_detail": {"product_id"},
        "robot_vacuum_compare": {"product_ids"},
        "robot_vacuum_knowledge_query": {"query", "category", "top_k"},
        "robot_vacuum_diagnosis": {"query", "product_id", "order_id", "user_has_checked", "want_repair"},
        "screenshot_order_review": {"evidence_ids", "customer_id", "session_id"},
        "aftersale_check": {"order_id", "customer_id", "ticket_type", "reason", "product_id", "application_time", "package_complete"},
        "ticket_create": {"order_id", "customer_id", "ticket_type", "reason", "product_id", "application_time", "package_complete", "force_create", "evidence_ids"},
    }

    allowed = allowed_by_intent.get(intent)
    if not allowed:
        return arguments

    effective = {key: value for key, value in arguments.items() if key in allowed}

    if intent == "aftersale_check":
        reason = effective.get("reason")
        if is_generic_reason(reason):
            ticket_name = ticket_type_display(arguments.get("ticket_type"))
            effective["reason"] = f"用户咨询该订单是否支持{ticket_name}"
        return effective

    if intent == "ticket_create":
        reason = effective.get("reason")
        if is_generic_reason(reason):
            raw_reason = arguments.get("raw_reason")
            if raw_reason and not is_generic_reason(raw_reason):
                reason = raw_reason
            else:
                reason = "用户申请售后"

        reason_parts = [reason]

        if arguments.get("product_name"):
            reason_parts.append(f"商品名称：{arguments['product_name']}")

        if arguments.get("package_status"):
            reason_parts.append(f"拆封/使用状态：{arguments['package_status']}")

        effective["reason"] = "；".join(reason_parts)

        if arguments.get("package_status") == "未拆封/未使用":
            effective["package_complete"] = True
        elif arguments.get("package_status") == "已拆封/已使用":
            effective["package_complete"] = False

    return effective
