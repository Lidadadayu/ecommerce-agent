from __future__ import annotations

from typing import Any

from agent.constants import ticket_type_display
from agent.rule_router import route_user_query
from tools.tool_registry import execute_tool


def _format_product_search(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "没有找到相关商品。")
    products = data.get("products", [])
    if not products:
        return "没有找到相关商品。"
    lines = [f"共找到 {len(products)} 个相关商品："]
    for item in products:
        lines.append(f"- {item.get('product_id')}｜{item.get('product_name')}｜{item.get('category')}｜{item.get('brand')}｜￥{item.get('price')}｜库存 {item.get('stock')}")
    return "\n".join(lines)


def _format_product_detail(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "商品详情查询失败。")
    p = data.get("product") or {}
    return (
        f"商品详情如下：\n- 商品 ID：{p.get('product_id')}\n- 商品名称：{p.get('product_name')}\n"
        f"- 类别：{p.get('category')}\n- 品牌：{p.get('brand')}\n- 价格：￥{p.get('price')}\n"
        f"- 库存：{p.get('stock')}\n- 状态：{p.get('status')}\n- 规格：{p.get('specs')}"
    )


def _format_order_query(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "订单查询失败。")
    order = data.get("order") or {}
    lines = [
        "订单详情如下：",
        f"- 订单号：{order.get('order_id')}",
        f"- 用户：{order.get('customer_name')}（{order.get('customer_level')}）",
        f"- 订单状态：{order.get('order_status')}",
        f"- 支付金额：￥{order.get('payment_amount')}",
        f"- 支付时间：{order.get('pay_time')}",
        f"- 发货时间：{order.get('ship_time')}",
        f"- 签收时间：{order.get('receive_time')}",
        "- 商品明细：",
    ]
    for item in order.get("items", []):
        lines.append(f"  - {item.get('product_id')}｜{item.get('product_name')}｜{item.get('category')}｜数量 {item.get('quantity')}｜单价 ￥{item.get('unit_price')}")
    return "\n".join(lines)


def _format_logistics_query(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "物流查询失败。")
    lines = [
        f"物流查询成功，当前状态：{data.get('current_status')}",
        f"最新位置：{data.get('latest_location')}",
        f"最新时间：{data.get('latest_event_time')}",
        "物流轨迹：",
    ]
    for item in data.get("logistics", []):
        lines.append(f"- {item.get('event_time')}｜{item.get('location')}｜{item.get('logistics_status')}｜{item.get('description')}")
    return "\n".join(lines)


def _format_policy_query(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "售后政策查询失败。")
    lines = [data.get("message", "售后政策如下：")]
    for p in data.get("policies", []):
        lines.append(f"- {p.get('title')}：{p.get('content')} 允许期限：{p.get('allow_days')} 天")
    return "\n".join(lines)


def _format_aftersale_check(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "售后资格判断失败。")
    rule = data.get("rule_result") or {}
    ticket_name = ticket_type_display(rule.get("ticket_type"))
    if data.get("eligible"):
        return (
            f"判断结果：可以申请售后。\n- 原因：{rule.get('reason')}\n- 适用政策：{rule.get('policy_title')}\n"
            f"- 商品类别：{rule.get('category')}\n- 售后类型：{ticket_name}\n- 已签收天数：{rule.get('elapsed_days')} 天\n- 允许期限：{rule.get('allow_days')} 天"
        )
    return (
        f"判断结果：暂不满足售后条件。\n- 原因：{data.get('message')}\n- 规则说明：{rule.get('reason')}\n"
        f"- 商品类别：{rule.get('category')}\n- 售后类型：{ticket_name}"
    )


def _format_ticket_create(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        eligibility = data.get("eligibility") or {}
        return f"工单未创建。\n- 原因：{data.get('message')}\n- 售后判断：{eligibility.get('message')}"
    ticket = data.get("ticket") or {}
    evidence_ids = data.get("evidence_ids") or []
    evidence_text = f"\n- 已关联凭证：{', '.join(evidence_ids)}" if evidence_ids else ""
    return (
        f"售后工单处理结果：{data.get('message')}\n- 工单号：{ticket.get('ticket_id')}\n- 订单号：{ticket.get('order_id')}\n"
        f"- 商品 ID：{ticket.get('product_id')}\n- 售后类型：{ticket_type_display(ticket.get('ticket_type'))}\n"
        f"- 工单状态：{ticket.get('ticket_status')}\n- 创建时间：{ticket.get('created_at')}"
        f"{evidence_text}"
    )


def _format_ticket_query(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "工单查询失败。")
    tickets = data.get("tickets", [])
    if not tickets:
        return "该订单暂时没有售后工单。"
    lines = [f"共找到 {len(tickets)} 个售后工单："]
    for t in tickets:
        lines.append(f"- 工单号：{t.get('ticket_id')}｜订单号：{t.get('order_id')}｜商品：{t.get('product_id')}｜类型：{ticket_type_display(t.get('ticket_type'))}｜状态：{t.get('ticket_status')}｜创建时间：{t.get('created_at')}")
    return "\n".join(lines)


def _format_recent_orders(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "最近订单查询失败。")
    orders = data.get("orders", [])
    if not orders:
        return "暂未查询到最近订单。"
    lines = [f"共找到 {len(orders)} 个最近订单："]
    for o in orders:
        lines.append(f"- {o.get('order_id')}｜用户：{o.get('customer_name')}｜状态：{o.get('order_status')}｜金额：￥{o.get('payment_amount')}｜商品数：{o.get('item_count')}｜创建时间：{o.get('created_at')}")
    return "\n".join(lines)


def _format_purchase_history(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "购买记录查询失败。")
    purchases = data.get("purchases", [])
    if not purchases:
        return "当前用户暂未查询到购买记录。"

    customer = data.get("customer") or {}
    lines = [
        f"{customer.get('customer_name') or data.get('customer_id') or '当前用户'} 的购买记录如下："
    ]
    for item in purchases:
        lines.append(
            f"- 订单号：{item.get('order_id')}｜商品：{item.get('product_id')} {item.get('product_name')}｜"
            f"类别：{item.get('category')}｜品牌：{item.get('brand')}｜数量：{item.get('quantity')}｜"
            f"单价：￥{item.get('unit_price')}｜订单金额：￥{item.get('payment_amount')}｜"
            f"订单状态：{item.get('order_status')}｜下单时间：{item.get('created_at')}｜签收时间：{item.get('receive_time')}"
        )
    return "\n".join(lines)


def _format_order_cancel(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return f"订单取消失败：{data.get('message', '暂时无法取消订单。')}\n如果订单已发货、已签收或状态异常，建议转人工客服处理。"
    return f"订单取消处理结果：{data.get('message')}\n- 订单号：{data.get('order_id')}\n- 原状态：{data.get('old_status')}\n- 新状态：{data.get('new_status')}\n- 原因：{data.get('reason')}\n\n提示：如果涉及已支付订单的真实退款，最终仍以平台支付和人工审核结果为准。"


def _format_shipment_urge(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "催发货处理失败。")
    return f"催发货处理结果：{data.get('message')}\n- 订单号：{data.get('order_id')}\n- 当前状态：{data.get('order_status')}\n- 原因：{data.get('reason', '用户催发货')}"


def _format_refund_progress(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "退款进度查询失败。")
    lines = [data.get("message", "退款/退货进度如下：")]
    for t in data.get("tickets", []):
        lines.append(f"- 工单号：{t.get('ticket_id')}｜类型：{t.get('ticket_type_name')}｜状态：{t.get('ticket_status')}｜进度：{t.get('progress_text')}｜更新时间：{t.get('updated_at')}")
    return "\n".join(lines)


def _format_operation_metrics(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "运营指标查询失败。")
    lines = [
        f"近 {data.get('days')} 天基础运营指标如下：",
        f"- 订单量：{data.get('order_count')}",
        f"- GMV：￥{data.get('gmv')}",
        f"- 售后工单量：{data.get('ticket_count')}",
        f"- 退款/退货相关工单量：{data.get('refund_related_count')}",
        f"- 待人工审核工单量：{data.get('pending_review_count')}",
        f"- 退款/退货工单率：{data.get('refund_ticket_rate')}",
        "- 订单状态分布：",
    ]
    for row in data.get("order_status_distribution", []):
        lines.append(f"  - {row.get('order_status')}：{row.get('count')}")
    return "\n".join(lines)


def _yes_no(value: Any) -> str:
    return "是" if bool(value) else "否"



def _format_screenshot_order_review(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "我还没有收到可识别的订单截图，请先在聊天输入区上传订单截图。")
    return data.get("message", "已识别订单截图，请告诉我你希望对该订单进行什么操作。")

def _format_robot_vacuum_search(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "扫地机器人商品检索失败。")

    products = data.get("products") or []
    if not products:
        return "暂未找到符合条件的扫地机器人商品。你可以放宽预算、户型或功能要求后再试。"

    lines = [f"根据你的需求，推荐以下 {len(products)} 款扫地机器人/扫拖一体机器人："]
    for index, item in enumerate(products, start=1):
        lines.append(f"{index}. {item.get('product_id')}｜{item.get('name')}｜￥{item.get('price')}")
        lines.append(f"   - 吸力：{item.get('suction_pa')}Pa；导航：{item.get('navigation')}；续航：{item.get('runtime_min')}分钟；适用面积：{item.get('suitable_area')}")
        lines.append(f"   - 拖地：{_yes_no(item.get('mop'))}；自动集尘：{_yes_no(item.get('auto_dust_collection'))}；自动洗拖布：{_yes_no(item.get('auto_mop_wash'))}；避障：{item.get('obstacle_avoidance')}")
        reasons = item.get("recommend_reasons") or []
        if reasons:
            lines.append(f"   - 推荐理由：{'；'.join(reasons)}")

    lines.append("")
    lines.append("如果你想进一步对比，可以直接说：对比 RV2001 和 RV4001。")
    return "\n".join(lines)


def _format_robot_vacuum_detail(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "扫地机器人商品详情查询失败。")

    p = data.get("product") or {}
    lines = [
        "扫地机器人商品详情如下：",
        f"- 商品 ID：{p.get('product_id')}",
        f"- 商品名称：{p.get('name')}",
        f"- 类别：{p.get('category')}",
        f"- 价格：￥{p.get('price')}",
        f"- 吸力：{p.get('suction_pa')}Pa",
        f"- 导航方式：{p.get('navigation')}",
        f"- 电池容量：{p.get('battery_mah')}mAh",
        f"- 续航时间：{p.get('runtime_min')}分钟",
        f"- 适用面积：{p.get('suitable_area')}",
        f"- 是否拖地：{_yes_no(p.get('mop'))}",
        f"- 自动集尘：{_yes_no(p.get('auto_dust_collection'))}",
        f"- 自动洗拖布：{_yes_no(p.get('auto_mop_wash'))}",
        f"- 热风烘干：{_yes_no(p.get('hot_air_drying'))}",
        f"- 避障方式：{p.get('obstacle_avoidance')}",
        f"- 保修期：{p.get('warranty_months')}个月",
        f"- 适合人群：{'、'.join(p.get('target_users') or [])}",
    ]
    return "\n".join(lines)


def _format_robot_vacuum_compare(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "扫地机器人商品对比失败。")

    items = data.get("comparison") or []
    lines = ["扫地机器人型号对比如下："]

    for item in items:
        lines.append("")
        lines.append(f"- {item.get('product_id')}｜{item.get('name')}")
        lines.append(f"  - 价格：￥{item.get('price')}；吸力：{item.get('suction_pa')}Pa；续航：{item.get('runtime_min')}分钟")
        lines.append(f"  - 导航：{item.get('navigation')}；避障：{item.get('obstacle_avoidance')}")
        lines.append(f"  - 适用面积：{item.get('suitable_area')}；保修：{item.get('warranty_months')}个月")
        lines.append(f"  - 拖地：{_yes_no(item.get('mop'))}；自动集尘：{_yes_no(item.get('auto_dust_collection'))}；自动洗拖布：{_yes_no(item.get('auto_mop_wash'))}；热风烘干：{_yes_no(item.get('hot_air_drying'))}")
        lines.append(f"  - 适合人群：{'、'.join(item.get('target_users') or [])}")

    lines.append("")
    lines.append("选择建议：如果预算优先，可以看价格较低的型号；如果想减少维护频率，优先选择自动集尘/自动洗拖布/热风烘干能力更完整的型号。")
    return "\n".join(lines)


def _format_robot_vacuum_knowledge_query(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "扫地机器人知识库检索失败。")

    chunks = data.get("chunks") or []
    if not chunks:
        return "知识库中暂未检索到足够相关的扫地机器人内容。你可以换一种说法，或补充具体现象、型号和使用场景。"

    lines = ["根据扫地机器人领域知识库，检索到以下相关内容："]
    for index, chunk in enumerate(chunks[:4], start=1):
        content = str(chunk.get("content") or "").strip()
        if len(content) > 260:
            content = content[:260] + "..."
        lines.append(f"{index}. {chunk.get('title')}（相关度：{chunk.get('score')}）")
        lines.append(f"   {content}")

    lines.append("")
    lines.append("我会基于以上知识给出排查建议；如果涉及电池鼓包、进水、烧焦味、严重异响或主板故障，请停止使用并联系售后。")
    return "\n".join(lines)


def _format_robot_vacuum_diagnosis(result: dict[str, Any]) -> str:
    data = result.get("result") or {}
    if not data.get("success"):
        return data.get("message", "故障诊断失败，请补充更具体的故障现象。")

    lines: list[str] = []

    lines.append(f"我先按“{data.get('fault_name', '通用故障')}”为你排查。")

    if data.get("safety_notice"):
        lines.append("")
        lines.append(f"安全提醒：{data['safety_notice']}")

    if data.get("product_id"):
        lines.append(f"当前型号：{data.get('product_id')}")
    else:
        lines.append("你还没有提供具体型号。不同型号的传感器、基站和水路结构可能不同，后续可以补充型号进一步判断。")

    lines.append("")
    lines.append("可能原因与自查步骤：")
    for idx, step in enumerate(data.get("self_check_steps") or [], start=1):
        lines.append(f"{idx}. {step}")

    lines.append("")
    lines.append("处理建议：")
    for idx, step in enumerate(data.get("repair_suggestions") or [], start=1):
        lines.append(f"{idx}. {step}")

    questions = data.get("follow_up_questions") or []
    if questions:
        lines.append("")
        lines.append("为了进一步判断，你可以补充：")
        for idx, question in enumerate(questions, start=1):
            lines.append(f"{idx}. {question}")

    if data.get("recommend_aftersale"):
        lines.append("")
        lines.append("售后建议：如果你按上面步骤检查后仍未恢复，建议提交维修/售后工单，由人工客服结合订单、保修期和故障凭证进一步处理。")

    rag_chunks = data.get("rag_chunks") or []
    if rag_chunks:
        lines.append("")
        lines.append("知识库参考：")
        for item in rag_chunks[:2]:
            lines.append(f"- {item.get('title')}")

    return "\n".join(lines)


def generate_answer(intent: str, tool_result: dict[str, Any]) -> str:
    if not tool_result.get("success"):
        return tool_result.get("message", "工具调用失败。")

    formatters = {
        "screenshot_order_review": _format_screenshot_order_review,
        "robot_vacuum_search": _format_robot_vacuum_search,
        "robot_vacuum_detail": _format_robot_vacuum_detail,
        "robot_vacuum_compare": _format_robot_vacuum_compare,
        "robot_vacuum_knowledge_query": _format_robot_vacuum_knowledge_query,
        "robot_vacuum_diagnosis": _format_robot_vacuum_diagnosis,
        "product_search": _format_product_search,
        "product_detail": _format_product_detail,
        "order_query": _format_order_query,
        "recent_orders": _format_recent_orders,
        "purchase_history": _format_purchase_history,
        "order_cancel": _format_order_cancel,
        "shipment_urge": _format_shipment_urge,
        "refund_progress": _format_refund_progress,
        "operation_metrics": _format_operation_metrics,
        "logistics_query": _format_logistics_query,
        "policy_query": _format_policy_query,
        "aftersale_check": _format_aftersale_check,
        "ticket_create": _format_ticket_create,
        "ticket_query": _format_ticket_query,
    }
    formatter = formatters.get(intent)
    return formatter(tool_result) if formatter else "请求已处理，但暂时没有对应的回复模板。"


def run_rule_agent(user_query: str) -> dict[str, Any]:
    route = route_user_query(user_query)
    state = {
        "user_query": user_query,
        "intent": route["intent"],
        "tool_name": route["tool_name"],
        "arguments": route["arguments"],
        "tool_result": None,
        "final_answer": "",
        "error": route["error"],
    }

    if route["error"]:
        state["final_answer"] = route["error"]
        return state

    tool_result = execute_tool(route["tool_name"], route["arguments"])
    state["tool_result"] = tool_result
    state["final_answer"] = generate_answer(route["intent"], tool_result)
    return state
