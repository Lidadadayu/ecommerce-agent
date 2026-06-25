from __future__ import annotations

from typing import Any

from agent.memory import SessionMemory
from agent.failure_recovery import build_recovery_reply, classify_tool_failure


def _inner_result(tool_result: dict[str, Any]) -> dict[str, Any]:
    result = tool_result.get("result")
    return result if isinstance(result, dict) else {}


def _message(tool_result: dict[str, Any]) -> str:
    data = _inner_result(tool_result)
    return str(data.get("message") or tool_result.get("message") or "")


def _is_success(tool_result: dict[str, Any]) -> bool:
    data = _inner_result(tool_result)
    if "success" in data:
        return bool(data.get("success"))
    return bool(tool_result.get("success"))


def _format_candidates_from_memory(memory: SessionMemory) -> str:
    candidates = memory.current_business_context.get("candidate_products") or []
    if not candidates:
        return ""

    lines = ["该订单包含以下商品："]
    for item in candidates:
        lines.append(
            f"- {item.get('product_id')}｜{item.get('product_name')}｜{item.get('category')}"
        )
    return "\n".join(lines)


def _set_pending(
    memory: SessionMemory,
    *,
    intent: str,
    tool_name: str | None,
    arguments: dict[str, Any],
    missing_slots: list[str],
) -> None:
    memory.set_pending_action(
        intent=intent,
        tool_name=tool_name,
        arguments=arguments,
        missing_slots=missing_slots,
    )


def handle_tool_result(
    *,
    intent: str,
    tool_name: str | None,
    arguments: dict[str, Any],
    tool_result: dict[str, Any],
    memory: SessionMemory,
) -> dict[str, Any] | None:
    """
    工具结果闭环处理器。

    作用：
    1. 把“缺槽型失败”转成继续追问。
    2. 把“业务不可自动处理”转成人工审核/人工客服建议。
    3. 避免把数据库异常、订单不存在、商品不匹配直接裸露给用户。
    4. 不覆盖正常成功结果；正常结果继续交给 rule_agent + LLM 润色。
    """

    data = _inner_result(tool_result)
    message = _message(tool_result)

    failure = classify_tool_failure(
        intent=intent,
        tool_name=tool_name,
        arguments=arguments,
        tool_result=tool_result,
    )
    if failure and failure.get("failure_type") not in {
        "order_not_found",
        "logistics_not_found",
        "rag_no_result",
    }:
        return {
            "handled": True,
            "mode": f"failure_recovery_{failure.get('failure_type')}",
            "final_answer": build_recovery_reply(failure, arguments=arguments),
            "failure": failure,
        }

    # ------------------------------------------------------------------
    # 工具本身异常
    # ------------------------------------------------------------------
    if not tool_result.get("success") and data is None:
        return {
            "handled": True,
            "mode": "tool_execution_error",
            "final_answer": (
                "系统调用业务工具时出现异常，暂时无法完成本次操作。\n"
                "你可以稍后重试；如果多次失败，建议转人工客服处理。"
            ),
        }

    # ------------------------------------------------------------------
    # 售后：多商品订单缺 product_id
    # ------------------------------------------------------------------
    if intent in {"aftersale_check", "ticket_create"}:
        rule_result = data.get("rule_result") or {}
        eligibility = data.get("eligibility") or {}
        nested_rule = eligibility.get("rule_result") or {}

        if "多个商品" in message and "product_id" in message:
            pending_arguments = dict(arguments)

            if rule_result.get("order_id"):
                pending_arguments["order_id"] = rule_result["order_id"]
            if nested_rule.get("order_id"):
                pending_arguments["order_id"] = nested_rule["order_id"]

            _set_pending(
                memory,
                intent=intent,
                tool_name=tool_name,
                arguments=pending_arguments,
                missing_slots=["product_id"],
            )

            candidate_text = _format_candidates_from_memory(memory)
            extra = f"\n\n{candidate_text}" if candidate_text else ""

            return {
                "handled": True,
                "mode": "tool_result_missing_product_id",
                "final_answer": (
                    "这个订单包含多个商品，我还不能确定你要处理哪一个商品。\n"
                    "请补充要售后的商品 ID，例如 P10001；如果不清楚商品 ID，也可以先描述商品名称。"
                    f"{extra}"
                ),
            }

        if "商品" in message and "不属于订单" in message:
            _set_pending(
                memory,
                intent=intent,
                tool_name=tool_name,
                arguments={k: v for k, v in arguments.items() if k != "product_id"},
                missing_slots=["product_id"],
            )

            return {
                "handled": True,
                "mode": "tool_result_invalid_product",
                "final_answer": (
                    f"{message}\n"
                    "请重新确认要售后的商品 ID。商品 ID 通常类似 P10001。"
                ),
            }

        if "超过" in message and "售后期限" in message:
            return {
                "handled": True,
                "mode": "aftersale_deadline_exceeded",
                "final_answer": (
                    f"{message}\n"
                    "按照当前规则，该订单暂不满足自动售后条件。"
                    "如果存在质量问题、物流异常、平台承诺或其他特殊情况，建议转人工客服复核。"
                ),
            }

        if "包装或配件不完整" in message:
            return {
                "handled": True,
                "mode": "aftersale_package_incomplete",
                "final_answer": (
                    f"{message}\n"
                    "如果商品存在质量问题，可以补充质量问题说明或相关凭证，由人工客服进一步审核。"
                ),
            }

        if "需要存在质量问题" in message or "不支持无理由售后" in message:
            return {
                "handled": True,
                "mode": "aftersale_need_quality_issue",
                "final_answer": (
                    f"{message}\n"
                    "请补充是否存在质量问题，例如无法使用、破损、故障、发错货等。"
                    "如果只是个人原因退换，可能无法通过自动售后规则。"
                ),
            }

    # ------------------------------------------------------------------
    # 订单不存在
    # ------------------------------------------------------------------
    if "未找到订单" in message:
        _set_pending(
            memory,
            intent=intent,
            tool_name=tool_name,
            arguments={k: v for k, v in arguments.items() if k != "order_id"},
            missing_slots=["order_id"],
        )

        return {
            "handled": True,
            "mode": "tool_result_order_not_found",
            "final_answer": (
                f"{message}\n"
                "请检查订单号是否输入正确。订单号格式通常类似 O202605010001。"
            ),
        }

    # ------------------------------------------------------------------
    # 商品不存在
    # ------------------------------------------------------------------
    if "未找到商品" in message:
        return {
            "handled": True,
            "mode": "tool_result_product_not_found",
            "final_answer": (
                f"{message}\n"
                "请检查商品 ID 是否正确，或者直接输入商品名称，我可以先帮你搜索相关商品。"
            ),
        }

    # ------------------------------------------------------------------
    # 物流记录不存在
    # ------------------------------------------------------------------
    if intent == "logistics_query" and "未找到" in message and "物流" in message:
        return {
            "handled": True,
            "mode": "logistics_not_found",
            "final_answer": (
                f"{message}\n"
                "可能原因包括：订单尚未发货、物流信息暂未同步，或订单号输入有误。"
                "你可以先查询订单详情确认订单状态。"
            ),
        }

    # ------------------------------------------------------------------
    # 售后政策不存在
    # ------------------------------------------------------------------
    if intent == "policy_query" and "未找到" in message and "售后政策" in message:
        return {
            "handled": True,
            "mode": "policy_not_found",
            "final_answer": (
                f"{message}\n"
                "请确认商品类别是否正确，例如数码配件、家用电器、生鲜食品或虚拟商品。"
                "如果属于特殊商品，建议转人工客服确认。"
            ),
        }

    # ------------------------------------------------------------------
    # 退款/退货进度不存在
    # ------------------------------------------------------------------
    if intent == "refund_progress" and "暂未查询到" in message:
        return {
            "handled": True,
            "mode": "refund_progress_not_found",
            "final_answer": (
                f"{message}\n"
                "如果你还没有提交退货或退款申请，可以先告诉我你要申请的售后类型和原因，我可以帮你做售后资格预判断。"
            ),
        }

    # ------------------------------------------------------------------
    # 取消订单失败
    # ------------------------------------------------------------------
    if intent == "order_cancel" and not _is_success(tool_result):
        return {
            "handled": True,
            "mode": "order_cancel_failed",
            "final_answer": (
                f"{message}\n"
                "如果订单已经发货、签收或关闭，系统通常不能自动取消。"
                "这类情况建议转人工客服处理，或根据订单状态走退货/退款流程。"
            ),
        }

    # ------------------------------------------------------------------
    # 催发货失败
    # ------------------------------------------------------------------
    if intent == "shipment_urge" and not _is_success(tool_result):
        return {
            "handled": True,
            "mode": "shipment_urge_failed",
            "final_answer": (
                f"{message}\n"
                "请先确认订单号是否正确，或者查询订单详情查看当前订单状态。"
            ),
        }

    return None
