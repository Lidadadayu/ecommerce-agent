from __future__ import annotations

import re
from typing import Any


DIAGNOSIS_WORDS = [
    "故障",
    "坏了",
    "怎么办",
    "不回充",
    "回充失败",
    "开机无反应",
    "无法开机",
    "不启动",
    "自动关机",
    "不出水",
    "拖地不出水",
    "建图失败",
    "地图丢失",
    "雷达异常",
    "吸力变小",
    "噪音",
    "异响",
    "APP连接不上",
    "配网失败",
    "维修",
    "修复",
    "检测",
]


def is_robot_diagnosis_query(text: str) -> bool:
    if not any(word in text for word in ["扫地机器人", "扫拖", "机器人", "基站", "拖布", "边刷", "主刷", "雷达"]):
        return False
    return any(word in text for word in DIAGNOSIS_WORDS)


def extract_robot_product_id(text: str) -> str | None:
    match = re.search(r"\bRV\d{4,}\b", text.upper())
    return match.group(0) if match else None


def build_robot_diagnosis_route(text: str) -> dict[str, Any]:
    return {
        "intent": "robot_vacuum_diagnosis",
        "tool_name": "robot_vacuum_diagnosis",
        "arguments": {
            "query": text,
            "product_id": extract_robot_product_id(text),
            "order_id": None,
            "user_has_checked": None,
            "want_repair": any(word in text for word in ["维修", "申请维修", "报修", "修一下"]),
        },
        "error": None,
    }
