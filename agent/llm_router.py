from __future__ import annotations

import json
import re
from typing import Any

from agent.rule_router import extract_ticket_type
from agent.llm_client import chat_with_llm


INTENT_TO_TOOL = {
    "order_query": "order_query",
    "recent_orders": "recent_orders",
    "order_cancel": "order_cancel",
    "shipment_urge": "shipment_urge",
    "refund_progress": "refund_progress",
    "operation_metrics": "operation_metrics",
    "logistics_query": "logistics_query",
    "ticket_query": "ticket_query",
    "purchase_history": "purchase_history",
    "aftersale_check": "aftersale_check",
    "ticket_create": "ticket_create",
    "product_detail": "product_detail",
    "product_search": "product_search",
    "policy_query": "policy_query",
    "robot_vacuum_search": "robot_vacuum_search",
    "robot_vacuum_detail": "robot_vacuum_detail",
    "robot_vacuum_compare": "robot_vacuum_compare",
    "robot_vacuum_knowledge_query": "robot_vacuum_knowledge_query",
    "robot_vacuum_diagnosis": "robot_vacuum_diagnosis",
}

VALID_INTENTS = set(INTENT_TO_TOOL)

CHINESE_TICKET_TYPE_MAP = {
    "退货": "return",
    "换货": "exchange",
    "维修": "repair",
    "退款": "refund",
    "取消": "cancel",
    "取消订单": "cancel",
}


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None

    text = text.strip()

    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return None

    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _normalize_ticket_type(value: Any, user_query: str) -> str | None:
    if not value:
        return extract_ticket_type(user_query)

    value = str(value).strip()
    if value in {"return", "exchange", "repair", "refund", "cancel"}:
        return value

    return CHINESE_TICKET_TYPE_MAP.get(value) or extract_ticket_type(user_query)


def _normalize_route(obj: dict[str, Any], user_query: str) -> dict[str, Any] | None:
    intent = obj.get("intent")
    if intent not in VALID_INTENTS:
        return None

    arguments = obj.get("arguments") or {}
    if not isinstance(arguments, dict):
        arguments = {}

    if intent in {"aftersale_check", "ticket_create"}:
        ticket_type = _normalize_ticket_type(arguments.get("ticket_type"), user_query)
        if ticket_type:
            arguments["ticket_type"] = ticket_type

        # 关键修正：
        # aftersale_check 不强行把用户问题写成 reason；
        # ticket_create 缺原因时才用用户原话兜底。
        if intent == "ticket_create" and not arguments.get("reason"):
            arguments["reason"] = user_query

    if intent == "product_search":
        keyword = arguments.get("keyword")
        if not keyword:
            return None
        arguments["keyword"] = str(keyword).strip()
        arguments["limit"] = int(arguments.get("limit") or 10)

    if intent == "robot_vacuum_search":
        arguments["query"] = str(arguments.get("query") or user_query).strip()
        for key in ["budget_max", "area_min", "top_k"]:
            if key in arguments and arguments[key] not in (None, ""):
                try:
                    arguments[key] = int(arguments[key])
                except (TypeError, ValueError):
                    arguments.pop(key, None)

    if intent == "robot_vacuum_detail":
        if not arguments.get("product_id"):
            return None
        arguments["product_id"] = str(arguments["product_id"]).strip().upper()

    if intent == "robot_vacuum_compare":
        ids = arguments.get("product_ids") or []
        if isinstance(ids, str):
            ids = [x.strip().upper() for x in ids.split(",") if x.strip()]
        arguments["product_ids"] = ids

    if intent == "robot_vacuum_knowledge_query":
        arguments["query"] = str(arguments.get("query") or user_query).strip()
        arguments["top_k"] = int(arguments.get("top_k") or 4)

    if intent == "robot_vacuum_diagnosis":
        arguments["query"] = str(arguments.get("query") or user_query).strip()
        if arguments.get("product_id"):
            arguments["product_id"] = str(arguments["product_id"]).strip().upper()

    if intent == "operation_metrics":
        try:
            arguments["days"] = int(arguments.get("days") or 30)
        except (TypeError, ValueError):
            arguments["days"] = 30

    if intent == "purchase_history":
        try:
            arguments["limit"] = int(arguments.get("limit") or 20)
        except (TypeError, ValueError):
            arguments["limit"] = 20

    return {
        "intent": intent,
        "tool_name": INTENT_TO_TOOL[intent],
        "arguments": arguments,
        "error": None,
        "source": "llm_router",
    }


def route_with_llm(user_query: str, memory_summary: str = "") -> dict[str, Any] | None:
    """
    LLM 兜底路由器。
    只输出结构化 intent/arguments，不直接回答用户。
    """

    prompt = f"""
你是电商售后与运营 Agent 的意图路由器。
你的任务是把用户问题转换成 JSON，不要直接回答用户。

当前会话上下文：
{memory_summary or "无"}

用户问题：
{user_query}

只能选择以下 intent：
1. product_search：商品搜索。参数：keyword, limit
2. product_detail：商品详情。参数：product_id
3. order_query：订单查询。参数：order_id
4. recent_orders：最近订单查询。参数：customer_id, limit
5. order_cancel：取消订单。参数：order_id, reason
6. shipment_urge：催发货。参数：order_id, reason
7. refund_progress：退款/退货进度查询。参数：order_id
8. operation_metrics：运营指标查询。参数：days
9. logistics_query：物流查询。参数：order_id
10. policy_query：售后政策查询。参数：category
11. aftersale_check：售后资格判断。参数：order_id, ticket_type, product_id
12. ticket_create：创建售后工单。参数：order_id, ticket_type, reason, product_id
13. ticket_query：查询售后工单。参数：order_id
14. purchase_history：查询当前登录用户购买过的商品。参数：customer_id, limit
15. robot_vacuum_search：扫地机器人售前推荐/选购。参数：query, budget_max, need_mop, need_auto_dust, need_auto_mop_wash, pet_family, area_min
16. robot_vacuum_detail：扫地机器人商品详情。参数：product_id，例如 RV2001
17. robot_vacuum_compare：扫地机器人型号对比。参数：product_ids，例如 ["RV2001", "RV4001"]
18. robot_vacuum_knowledge_query：扫地机器人维护保养/售后政策/通用知识查询。参数：query, category, top_k
19. robot_vacuum_diagnosis：扫地机器人结构化故障诊断。参数：query, product_id, order_id, user_has_checked, want_repair

售后类型 ticket_type 只能使用：
return, exchange, repair, refund, cancel

判断原则：
- “可以退吗 / 能不能退款 / 支持换货吗”属于 aftersale_check，不要把用户问题当 reason。
- “我要退货 / 帮我申请退款 / 创建工单 / 提交售后”属于 ticket_create。
- “取消订单”属于 order_cancel，不属于 ticket_create。
- “催发货 / 怎么还不发货”属于 shipment_urge。
- “退款进度 / 钱退了吗”属于 refund_progress。
- “我买过哪些商品 / 购买记录 / 消费记录”属于 purchase_history。
- 用户没有明确提供订单号时，不要编造 order_id。
- 用户没有明确提供商品 ID 时，不要编造 product_id。
- 商品搜索可以提取自然语言关键词，例如“无线降噪耳机”。
- 扫地机器人推荐、选购、预算、养宠、大户型等问题优先使用 robot_vacuum_search。
- 扫地机器人不回充、不出水、建图失败、雷达异常、异响、无法开机等具体故障现象优先使用 robot_vacuum_diagnosis。
- 扫地机器人维护保养、耗材更换、售后政策等知识性问题优先使用 robot_vacuum_knowledge_query。
- 扫地机器人 RV2001 这类型号详情用 robot_vacuum_detail；多个 RV 型号对比用 robot_vacuum_compare。
- 无法判断就输出 intent 为 unknown。

只输出 JSON。
"""

    result = chat_with_llm(
        user_query=prompt,
        temperature=0.0,
        max_tokens=400,
        fallback_content='{"intent": "unknown", "arguments": {}}',
    )

    obj = _extract_json_object(result.get("content") or "")
    if not obj:
        return None

    return _normalize_route(obj, user_query)
