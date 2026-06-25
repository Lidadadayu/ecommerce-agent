from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from tools.business_tools import (
    cancel_order,
    check_aftersale_eligibility,
    create_aftersale_ticket,
    get_logistics,
    get_operation_metrics,
    get_order_detail,
    get_customer_purchases,
    get_policies_by_category,
    get_product_detail,
    get_recent_orders,
    get_refund_progress,
    get_tickets_by_order,
    search_products,
    urge_shipment,
)
from tools.robot_vacuum_diagnosis import diagnose_robot_vacuum_fault
from tools.robot_vacuum_tools import (
    compare_robot_vacuum_products,
    get_robot_vacuum_product_detail,
    query_robot_vacuum_knowledge,
    search_robot_vacuum_products,
)
from agent.screenshot_parser import review_order_screenshot
from agent.intent_slot_extractor import extract_intent_slots


@dataclass
class ToolSpec:
    name: str
    description: str
    function: Callable[..., dict]
    parameters: dict[str, Any]


def _to_jsonable(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(obj, date):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]
    return obj


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "robot_vacuum_search": ToolSpec(
        "robot_vacuum_search",
        "根据预算、户型、是否养宠、是否需要扫拖/自动集尘等条件推荐扫地机器人。",
        search_robot_vacuum_products,
        {
            "query": "用户原始需求",
            "budget_max": "最高预算，可选",
            "need_mop": "是否需要拖地",
            "need_auto_dust": "是否需要自动集尘",
            "need_auto_mop_wash": "是否需要自动洗拖布",
            "pet_family": "是否养宠",
            "area_min": "户型面积，可选",
        },
    ),
    "robot_vacuum_detail": ToolSpec(
        "robot_vacuum_detail",
        "查询扫地机器人商品详情。",
        get_robot_vacuum_product_detail,
        {"product_id": "扫地机器人商品 ID，例如 RV2001"},
    ),
    "robot_vacuum_compare": ToolSpec(
        "robot_vacuum_compare",
        "对比多个扫地机器人型号。",
        compare_robot_vacuum_products,
        {"product_ids": "扫地机器人商品 ID 列表，例如 ['RV2001','RV4001']"},
    ),
    "robot_vacuum_knowledge_query": ToolSpec(
        "robot_vacuum_knowledge_query",
        "检索扫地机器人售前、故障、维护、售后政策知识。",
        query_robot_vacuum_knowledge,
        {"query": "用户问题", "category": "知识类别，可选", "top_k": "返回条数"},
    ),
    "robot_vacuum_diagnosis": ToolSpec(
        "robot_vacuum_diagnosis",
        "对扫地机器人/扫拖一体机器人故障进行结构化诊断，给出自查步骤、修复建议和售后建议。",
        diagnose_robot_vacuum_fault,
        {
            "query": "用户故障描述",
            "product_id": "扫地机器人商品 ID，可选",
            "order_id": "订单号，可选",
            "user_has_checked": "用户已经检查过的内容，可选",
            "want_repair": "是否明确想申请维修，可选",
        },
    ),
    "screenshot_order_review": ToolSpec(
        "screenshot_order_review",
        "识别当前会话上传的订单截图，提取订单信息并追问用户下一步要办理的操作。",
        review_order_screenshot,
        {
            "evidence_ids": "当前会话上传的订单截图凭证 ID 列表",
            "customer_id": "用户 ID，可选",
            "session_id": "会话 ID，可选",
        },
    ),
    "intent_slot_extract": ToolSpec(
        "intent_slot_extract",
        "对用户问题进行轻量级意图识别和槽位抽取，返回缺失槽位与推荐工具。",
        extract_intent_slots,
        {"user_query": "用户原始问题", "memory": "会话记忆，可选"},
    ),
    "product_search": ToolSpec("product_search", "根据关键词搜索商品。", search_products, {"keyword": "搜索关键词", "limit": "返回数量"}),
    "product_detail": ToolSpec("product_detail", "根据商品 ID 查询商品详情。", get_product_detail, {"product_id": "商品 ID"}),
    "order_query": ToolSpec("order_query", "根据订单 ID 查询订单详情。", get_order_detail, {"order_id": "订单 ID", "customer_id": "用户 ID，可选"}),
    "recent_orders": ToolSpec("recent_orders", "查询最近订单。", get_recent_orders, {"customer_id": "用户 ID，可选", "limit": "返回数量"}),
    "purchase_history": ToolSpec("purchase_history", "查询当前用户购买过的商品记录。", get_customer_purchases, {"customer_id": "用户 ID", "limit": "返回数量"}),
    "order_cancel": ToolSpec("order_cancel", "取消未发货或未签收的订单。", cancel_order, {"order_id": "订单 ID", "reason": "取消原因", "customer_id": "用户 ID，可选"}),
    "shipment_urge": ToolSpec("shipment_urge", "记录催发货需求。", urge_shipment, {"order_id": "订单 ID", "reason": "催发货原因", "customer_id": "用户 ID，可选"}),
    "refund_progress": ToolSpec("refund_progress", "查询退款/退货进度。", get_refund_progress, {"order_id": "订单 ID", "customer_id": "用户 ID，可选"}),
    "operation_metrics": ToolSpec("operation_metrics", "查询基础运营指标。", get_operation_metrics, {"days": "统计天数"}),
    "logistics_query": ToolSpec("logistics_query", "查询物流轨迹和当前状态。", get_logistics, {"order_id": "订单 ID", "customer_id": "用户 ID，可选"}),
    "policy_query": ToolSpec("policy_query", "根据商品类别查询售后政策。", get_policies_by_category, {"category": "商品类别"}),
    "ticket_query": ToolSpec("ticket_query", "根据订单 ID 查询售后工单。", get_tickets_by_order, {"order_id": "订单 ID", "customer_id": "用户 ID，可选"}),
    "aftersale_check": ToolSpec(
        "aftersale_check",
        "判断是否满足售后条件。",
        check_aftersale_eligibility,
        {
            "order_id": "订单 ID",
            "customer_id": "用户 ID，可选",
            "ticket_type": "售后类型",
            "reason": "原因",
            "product_id": "商品 ID，可选",
            "application_time": "申请时间，可选",
            "package_complete": "包装是否完整",
        },
    ),
    "ticket_create": ToolSpec(
        "ticket_create",
        "创建售后工单。",
        create_aftersale_ticket,
        {
            "order_id": "订单 ID",
            "customer_id": "用户 ID，可选",
            "ticket_type": "售后类型",
            "reason": "原因",
            "product_id": "商品 ID，可选",
            "application_time": "申请时间，可选",
            "package_complete": "包装是否完整",
            "force_create": "是否强制创建",
            "evidence_ids": "售后凭证 ID 列表，可选",
        },
    ),
}


def list_tools() -> list[dict[str, Any]]:
    return [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in TOOL_REGISTRY.values()]


def get_tool_spec(tool_name: str) -> ToolSpec | None:
    return TOOL_REGISTRY.get(tool_name)


def execute_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict:
    arguments = arguments or {}
    tool = get_tool_spec(tool_name)
    if tool is None:
        return {"success": False, "tool_name": tool_name, "message": f"未知工具：{tool_name}", "result": None}

    try:
        result = tool.function(**arguments)
        return {"success": True, "tool_name": tool_name, "message": "工具调用成功", "result": _to_jsonable(result)}
    except TypeError as exc:
        return {"success": False, "tool_name": tool_name, "message": f"工具参数错误：{exc}", "result": None}
    except Exception as exc:
        return {"success": False, "tool_name": tool_name, "message": f"工具执行失败：{exc}", "result": None}
