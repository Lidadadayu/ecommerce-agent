from __future__ import annotations

import re
from typing import Any

from agent.constants import CATEGORY_KEYWORDS, PRODUCT_KEYWORDS
from agent.domain_loader import get_domain_keywords
from agent.patterns import extract_order_id, extract_product_id


ROBOT_VACUUM_WORDS = get_domain_keywords("product_words")
ROBOT_PRESALES_WORDS = get_domain_keywords("presales_words")
ROBOT_FAULT_WORDS = get_domain_keywords("fault_words")
ROBOT_MAINTENANCE_WORDS = get_domain_keywords("maintenance_words")
ROBOT_AFTERSALE_WORDS = get_domain_keywords("aftersales_words")

DIAGNOSIS_WORDS = [
    "故障", "坏了", "怎么办", "不回充", "回充失败", "开机无反应", "无法开机", "不启动",
    "自动关机", "不出水", "拖地不出水", "建图失败", "地图丢失", "雷达异常", "吸力变小",
    "噪音", "异响", "APP连接不上", "配网失败", "维修", "修复", "检测", "烧焦", "冒烟",
    "进水", "电池鼓包",
]


def _contains_any(text: str, words: list[str]) -> bool:
    lower = text.lower()
    return any(w.lower() in lower for w in words)


def is_robot_vacuum_query(text: str) -> bool:
    return _contains_any(text, ROBOT_VACUUM_WORDS) or _contains_any(text, ROBOT_FAULT_WORDS)


def is_robot_diagnosis_query(text: str) -> bool:
    if not _contains_any(text, ROBOT_VACUUM_WORDS + ["扫拖", "基站", "拖布", "边刷", "主刷", "雷达"]):
        return False
    return _contains_any(text, DIAGNOSIS_WORDS)


def extract_robot_product_ids(text: str) -> list[str]:
    ids = re.findall(r"\bRV\d{4,}\b", text.upper())
    seen: set[str] = set()
    return [pid for pid in ids if not (pid in seen or seen.add(pid))]


def extract_budget_max(text: str) -> int | None:
    patterns = [
        r"预算\s*(\d{3,5})",
        r"(\d{3,5})\s*元?\s*以内",
        r"不超过\s*(\d{3,5})",
        r"(\d{3,5})\s*以下",
        r"低于\s*(\d{3,5})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                value = int(match.group(1))
                if 300 <= value <= 20000:
                    return value
            except ValueError:
                pass
    return None


def extract_area_min(text: str) -> int | None:
    match = re.search(r"(\d{2,3})\s*(?:平|㎡|平方)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def build_robot_search_arguments(text: str) -> dict[str, Any]:
    return {
        "query": text,
        "budget_max": extract_budget_max(text),
        "need_mop": True if _contains_any(text, ["拖地", "扫拖", "扫拖一体", "拖布", "水箱"]) else None,
        "need_auto_dust": True if "自动集尘" in text or "集尘" in text else None,
        "need_auto_mop_wash": True if _contains_any(text, ["自动洗拖布", "洗拖布", "全能基站", "自动清洗"]) else None,
        "pet_family": True if _contains_any(text, ["养宠", "宠物", "猫", "狗", "毛发"]) else None,
        "area_min": extract_area_min(text),
    }


def build_robot_diagnosis_arguments(text: str) -> dict[str, Any]:
    ids = extract_robot_product_ids(text)
    return {
        "query": text,
        "product_id": ids[0] if ids else None,
        "order_id": extract_order_id(text),
        "user_has_checked": None,
        "want_repair": any(word in text for word in ["维修", "申请维修", "报修", "修一下"]),
    }


def infer_robot_knowledge_category(text: str) -> str | None:
    if _contains_any(text, ROBOT_MAINTENANCE_WORDS):
        return "robot_vacuum_maintenance"
    if _contains_any(text, ROBOT_AFTERSALE_WORDS):
        return "robot_vacuum_aftersale_policy"
    if _contains_any(text, ROBOT_FAULT_WORDS):
        return "robot_vacuum_troubleshooting"
    if _contains_any(text, ROBOT_PRESALES_WORDS):
        return "robot_vacuum_buying_guide"
    return None


def extract_category(text: str) -> str | None:
    if is_robot_vacuum_query(text):
        return "扫地机器人"
    return next((c for c in CATEGORY_KEYWORDS if c in text), None)


def extract_days(text: str, default: int = 30) -> int:
    for p in [r"近\s*(\d+)\s*天", r"最近\s*(\d+)\s*天", r"(\d+)\s*天内"]:
        m = re.search(p, text)
        if m:
            try:
                return max(1, min(int(m.group(1)), 365))
            except ValueError:
                return default
    return default


def extract_product_keyword(text: str) -> str | None:
    for kw in PRODUCT_KEYWORDS:
        if kw.lower() in text.lower():
            return kw
    for p in [r"有没有(.+?)(?:商品|卖|推荐|$)", r"想买(.+?)(?:商品|$)", r"搜索(.+?)(?:商品|$)", r"查询(.+?)(?:商品|$)", r"找一下(.+?)(?:商品|$)"]:
        m = re.search(p, text)
        if m:
            v = m.group(1).strip(" ，。！？!?")
            if 1 <= len(v) <= 30:
                return v
    return None


def extract_ticket_type(text: str) -> str | None:
    if any(w in text for w in ["取消订单", "取消"]):
        return "cancel"
    if any(w in text for w in ["退款", "退钱"]):
        return "refund"
    if any(w in text for w in ["退货", "退掉", "退回"]):
        return "return"
    if any(w in text for w in ["换货", "更换", "换一个"]):
        return "exchange"
    if any(w in text for w in ["维修", "修理", "修一下", "故障", "坏了", "无法启动", "不能启动"]):
        return "repair"
    return None


def is_check_question(text: str) -> bool:
    words = ["可以吗", "行吗", "能不能", "能否", "是否可以", "可不可以", "还能", "能退", "能换", "能修", "可以退", "可以换", "可以维修", "能申请", "可以申请", "支持退", "支持换", "支持维修", "支持退款"]
    return any(w in text for w in words) or text.strip().endswith(("吗", "么", "？", "?"))


def is_create_ticket_request(text: str) -> bool:
    if is_check_question(text):
        return False
    words = ["创建工单", "生成工单", "提交工单", "提交申请", "帮我申请", "我要申请", "申请售后", "申请退货", "申请换货", "申请维修", "申请退款", "我要退货", "我想退货", "需要退货", "帮我退货", "办理退货", "给我退货", "我要换货", "我想换货", "需要换货", "我要维修", "我想维修", "需要维修", "我要退款", "我想退款", "需要退款"]
    return any(w in text for w in words)


def _need_order_error(intent: str, msg: str) -> dict[str, Any]:
    return {"intent": intent, "tool_name": None, "arguments": {}, "error": msg}


def route_user_query(user_query: str) -> dict[str, Any]:
    text = user_query.strip()
    if not text:
        return {"intent": "unknown", "tool_name": None, "arguments": {}, "error": "请输入你的问题，例如订单查询、物流查询或售后申请。"}

    order_id = extract_order_id(text)
    product_id = extract_product_id(text)
    robot_product_ids = extract_robot_product_ids(text)
    category = extract_category(text)
    product_keyword = extract_product_keyword(text)
    ticket_type = extract_ticket_type(text)

    if any(w in text for w in ["订单截图", "截图", "图片", "凭证", "上传的图", "上传图片"]) and any(
        w in text for w in ["识别", "看看", "帮我看", "帮我看看", "订单信息", "这个订单", "处理", "上传", "能不能退", "能不能换", "还能不能"]
    ):
        return {
            "intent": "screenshot_order_review",
            "tool_name": "screenshot_order_review",
            "arguments": {},
            "error": None,
        }

    if robot_product_ids and _contains_any(text, ["对比", "比较", "区别", "哪个好", "参数差异"]):
        if len(robot_product_ids) < 2:
            return {"intent": "robot_vacuum_compare", "tool_name": None, "arguments": {"product_ids": robot_product_ids}, "error": "扫地机器人型号对比至少需要提供两个商品 ID，例如 RV2001 和 RV4001。"}
        return {"intent": "robot_vacuum_compare", "tool_name": "robot_vacuum_compare", "arguments": {"product_ids": robot_product_ids}, "error": None}

    if robot_product_ids and _contains_any(text, ["详情", "参数", "介绍", "多少钱", "价格", "配置"]):
        return {"intent": "robot_vacuum_detail", "tool_name": "robot_vacuum_detail", "arguments": {"product_id": robot_product_ids[0]}, "error": None}

    if is_robot_vacuum_query(text):
        if is_robot_diagnosis_query(text):
            return {"intent": "robot_vacuum_diagnosis", "tool_name": "robot_vacuum_diagnosis", "arguments": build_robot_diagnosis_arguments(text), "error": None}

        if _contains_any(text, ROBOT_FAULT_WORDS + ROBOT_MAINTENANCE_WORDS + ROBOT_AFTERSALE_WORDS):
            return {
                "intent": "robot_vacuum_knowledge_query",
                "tool_name": "robot_vacuum_knowledge_query",
                "arguments": {"query": text, "category": infer_robot_knowledge_category(text), "top_k": 4},
                "error": None,
            }

        if _contains_any(text, ROBOT_PRESALES_WORDS) or _contains_any(text, ["买", "选"]):
            return {"intent": "robot_vacuum_search", "tool_name": "robot_vacuum_search", "arguments": build_robot_search_arguments(text), "error": None}

        return {
            "intent": "robot_vacuum_knowledge_query",
            "tool_name": "robot_vacuum_knowledge_query",
            "arguments": {"query": text, "category": infer_robot_knowledge_category(text), "top_k": 4},
            "error": None,
        }

    if any(w in text for w in ["运营数据", "运营指标", "GMV", "销售额", "订单量", "退款率", "售后率", "客诉"]):
        return {"intent": "operation_metrics", "tool_name": "operation_metrics", "arguments": {"days": extract_days(text)}, "error": None}

    if any(w in text for w in ["买过哪些", "购买过哪些", "购买记录", "消费记录", "买了哪些", "买过什么", "我买过"]):
        return {"intent": "purchase_history", "tool_name": "purchase_history", "arguments": {"limit": 20}, "error": None}

    if any(w in text for w in ["最近订单", "历史订单", "我的订单", "订单列表", "查一下订单列表"]):
        return {"intent": "recent_orders", "tool_name": "recent_orders", "arguments": {"limit": 5}, "error": None}

    if any(w in text for w in ["取消订单", "取消这个订单", "帮我取消"]):
        if not order_id:
            return _need_order_error("order_cancel", "取消订单需要提供订单号，例如 O202605010001。")
        return {"intent": "order_cancel", "tool_name": "order_cancel", "arguments": {"order_id": order_id, "reason": text}, "error": None}

    if any(w in text for w in ["催发货", "催一下发货", "怎么还不发货", "快点发货", "尽快发货"]):
        if not order_id:
            return _need_order_error("shipment_urge", "催发货需要提供订单号，例如 O202605010001。")
        return {"intent": "shipment_urge", "tool_name": "shipment_urge", "arguments": {"order_id": order_id, "reason": text}, "error": None}

    if any(w in text for w in ["退款进度", "退款状态", "退款到哪", "钱退了吗", "退货进度", "退货状态"]):
        if not order_id:
            return _need_order_error("refund_progress", "查询退款或退货进度需要提供订单号，例如 O202605010001。")
        return {"intent": "refund_progress", "tool_name": "refund_progress", "arguments": {"order_id": order_id}, "error": None}

    if "工单" in text and any(w in text for w in ["查", "查询", "进度", "状态", "有没有"]):
        if not order_id:
            return _need_order_error("ticket_query", "查询售后工单需要提供订单号，例如 O202605010001。")
        return {"intent": "ticket_query", "tool_name": "ticket_query", "arguments": {"order_id": order_id}, "error": None}

    if ticket_type and is_check_question(text):
        args = {"ticket_type": ticket_type, "reason": text}
        if order_id:
            args["order_id"] = order_id
        if product_id:
            args["product_id"] = product_id
        return {"intent": "aftersale_check", "tool_name": "aftersale_check" if order_id else None, "arguments": args, "error": None if order_id else "判断售后资格需要提供订单号，例如 O202605010001。"}

    if ticket_type and is_create_ticket_request(text):
        args = {"ticket_type": ticket_type, "reason": text}
        if order_id:
            args["order_id"] = order_id
        if product_id:
            args["product_id"] = product_id
        return {"intent": "ticket_create", "tool_name": "ticket_create" if order_id else None, "arguments": args, "error": None if order_id else "创建售后工单需要提供订单号，例如 O202605010001。"}

    if any(w in text for w in ["物流", "快递", "到哪", "运输", "签收", "配送"]):
        if not order_id:
            return _need_order_error("logistics_query", "查询物流需要提供订单号，例如 O202605010001。")
        return {"intent": "logistics_query", "tool_name": "logistics_query", "arguments": {"order_id": order_id}, "error": None}

    if order_id and any(w in text for w in ["订单", "状态", "买了", "详情", "支付", "发货", "查"]):
        return {"intent": "order_query", "tool_name": "order_query", "arguments": {"order_id": order_id}, "error": None}

    if "订单" in text and any(w in text for w in ["查", "查询", "状态", "详情", "支付", "发货"]):
        return _need_order_error("order_query", "查询订单需要提供订单号，例如 O202605010001。")

    if product_id:
        return {"intent": "product_detail", "tool_name": "product_detail", "arguments": {"product_id": product_id}, "error": None}

    if any(w in text for w in ["政策", "规则", "售后", "退换货"]):
        if not category:
            return {"intent": "policy_query", "tool_name": None, "arguments": {}, "error": "查询售后政策需要说明商品类别，例如数码配件、家用电器、生鲜食品或虚拟商品。"}
        return {"intent": "policy_query", "tool_name": "policy_query", "arguments": {"category": category}, "error": None}

    if product_keyword:
        return {"intent": "product_search", "tool_name": "product_search", "arguments": {"keyword": product_keyword, "limit": 10}, "error": None}

    return {"intent": "unknown", "tool_name": None, "arguments": {}, "error": "暂时无法识别你的需求。你可以尝试询问商品、订单、物流、售后政策或工单相关问题。"}
