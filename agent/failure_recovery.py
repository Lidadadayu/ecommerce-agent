from __future__ import annotations

from typing import Any

from agent.memory import extract_order_id


def classify_tool_failure(
    *,
    intent: str | None,
    tool_name: str | None,
    arguments: dict[str, Any],
    tool_result: dict[str, Any],
) -> dict[str, Any] | None:
    data = tool_result.get("result")
    data = data if isinstance(data, dict) else {}
    message = str(data.get("message") or tool_result.get("message") or "")
    if tool_result.get("success") and data.get("success", True) is not False:
        return None

    if "未找到订单" in message:
        return {"failure_type": "order_not_found", "recoverable": True, "message": message}
    if "格式错误" in message or (arguments.get("order_id") and not extract_order_id(str(arguments.get("order_id")))):
        return {"failure_type": "invalid_order_id", "recoverable": True, "message": message}
    if intent == "logistics_query" and "物流" in message and "未找到" in message:
        return {"failure_type": "logistics_not_found", "recoverable": True, "message": message}
    if intent in {"robot_vacuum_knowledge_query", "policy_query"} and ("未检索" in message or "未找到" in message):
        return {"failure_type": "rag_no_result", "recoverable": True, "message": message}
    if intent == "screenshot_order_review" and ("视觉" in message or "截图" in message):
        return {"failure_type": "vision_failed", "recoverable": True, "message": message}
    if "冲突" in message or "人工" in message:
        return {"failure_type": "rule_conflict", "recoverable": True, "message": message}
    return {"failure_type": "tool_exception", "recoverable": False, "message": message or "工具调用失败"}


def build_recovery_reply(failure: dict[str, Any], *, arguments: dict[str, Any]) -> str:
    kind = failure.get("failure_type")
    message = failure.get("message") or ""
    if kind == "order_not_found":
        order_id = arguments.get("order_id")
        suffix = f"当前识别到的订单号是 {order_id}。" if order_id else ""
        return f"{message}\n{suffix}请确认订单号是否正确，或重新上传订单截图。"
    if kind == "invalid_order_id":
        return "订单号格式看起来不正确。请提供类似 O202605010001 的订单号，或上传订单截图让我重新识别。"
    if kind == "logistics_not_found":
        return f"{message}\n我建议先查询订单详情确认是否已经发货；如果已发货但无物流记录，可转人工客服核实。"
    if kind == "rag_no_result":
        return f"{message}\n知识库没有直接命中条款，我会先按通用售后规则解释；涉及具体订单仍以订单状态和人工审核为准。"
    if kind == "vision_failed":
        return f"{message}\n截图凭证已保留。你可以手动补充订单号，我会继续校验数据库订单。"
    if kind == "rule_conflict":
        return f"{message}\n规则结果存在不确定性，建议转人工审核，避免误处理。"
    return f"系统工具暂时不可用：{message}\n你可以稍后重试；多次失败时建议转人工客服处理。"
