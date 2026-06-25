from __future__ import annotations

from typing import Any


def format_robot_vacuum_diagnosis(tool_result: dict[str, Any]) -> str:
    """
    将 robot_vacuum_diagnosis 工具结果转换为客服可读回答。

    可把该函数复制到 agent/rule_agent.py 中，然后在 formatters 字典加入：
        "robot_vacuum_diagnosis": format_robot_vacuum_diagnosis,
    """

    data = tool_result.get("result") or tool_result
    if not data.get("success"):
        return data.get("message", "故障诊断失败，请补充更具体的故障现象。")

    lines = []

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
