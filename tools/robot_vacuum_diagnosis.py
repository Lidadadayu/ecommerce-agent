from __future__ import annotations

import re
from typing import Any


SAFETY_STOP_WORDS = [
    "冒烟",
    "烧焦",
    "焦味",
    "异味",
    "进水",
    "泡水",
    "电池鼓包",
    "鼓包",
    "漏液",
    "充电发烫",
    "严重发热",
    "火花",
    "短路",
]


FAULT_PATTERNS: list[dict[str, Any]] = [
    {
        "fault_type": "power_no_response",
        "name": "开机无反应/指示灯不亮",
        "keywords": ["开机无反应", "开不了机", "无法开机", "指示灯不亮", "没反应", "不启动", "无法启动"],
        "questions": [
            "充电座指示灯是否亮起？",
            "机器人放到充电座后是否有充电提示音或指示灯变化？",
            "电源线、适配器和插座是否已更换测试？",
        ],
        "self_check": [
            "确认充电座电源线插紧，插座有电。",
            "检查电源适配器和电源线是否破损。",
            "将机器人重新放回充电座，确保充电触点对齐。",
            "擦拭机器人和充电座金属触点后再充电 30 分钟以上。",
        ],
        "repair": [
            "如果充电后仍无反应，可能涉及电池、充电模块或主板异常，建议联系售后检测。",
            "不要自行拆机更换主板或电池，以免影响保修和安全。",
        ],
        "risk_level": "medium",
        "suggest_ticket_type": "repair",
    },
    {
        "fault_type": "auto_shutdown",
        "name": "开机后自动关机",
        "keywords": ["自动关机", "刚开机就关机", "开机后关机", "用一会关机"],
        "questions": [
            "是否刚充满电后也会自动关机？",
            "机身是否明显发热？",
            "电池是否有鼓包、异味或漏液现象？",
        ],
        "self_check": [
            "先充满电后重试。",
            "将机器移到通风处冷却后再启动。",
            "检查尘盒、主刷、边刷是否卡死导致过载保护。",
        ],
        "repair": [
            "如果电池鼓包、异味或漏液，应立即停止使用并联系售后更换原装电池。",
            "如果冷却和清理后仍自动关机，建议售后检测电池和主板。",
        ],
        "risk_level": "high",
        "suggest_ticket_type": "repair",
    },
    {
        "fault_type": "return_to_dock_failed",
        "name": "不回充/回充失败/找不到基站",
        "keywords": ["不回充", "回充失败", "找不到基站", "找不到充电座", "回不了充", "无法回充", "回充传感器"],
        "questions": [
            "充电座周围 0.5 米左右是否有障碍物？",
            "充电座是否靠墙放置且没有被移动？",
            "机器人是否能正常建图和定位？",
        ],
        "self_check": [
            "将充电座靠墙放置，左右和前方留出空旷空间。",
            "清理充电座附近障碍物、电源线、地毯边缘等干扰物。",
            "擦拭机器人回充传感器和充电座红外/金属触点。",
            "在 APP 中重新定位或重新建图后再测试回充。",
        ],
        "repair": [
            "如果多次回充失败且传感器报警，可能是回充传感器、定位模块或充电座异常，建议售后检测。",
        ],
        "risk_level": "medium",
        "suggest_ticket_type": "repair",
    },
    {
        "fault_type": "no_water",
        "name": "拖地不出水/水箱异常",
        "keywords": ["不出水", "拖地不出水", "水箱不出水", "拖布不湿", "出水少", "不喷水"],
        "questions": [
            "水箱是否已加水并安装到位？",
            "APP 中出水量是否设置为关闭或低档？",
            "拖布、水箱出水孔是否有堵塞或水垢？",
        ],
        "self_check": [
            "确认水箱有水且安装到位。",
            "在 APP 中调高出水量，确认没有关闭拖地功能。",
            "清洗拖布和水箱出水孔，检查是否被水垢或异物堵塞。",
            "不要加入清洁剂、消毒液等非官方允许液体，避免堵塞水路。",
        ],
        "repair": [
            "如果清洗后仍不出水，可能是水泵或电控阀异常，建议提交维修工单。",
        ],
        "risk_level": "medium",
        "suggest_ticket_type": "repair",
    },
    {
        "fault_type": "mapping_failed",
        "name": "建图失败/地图丢失/定位异常",
        "keywords": ["建图失败", "地图丢失", "地图不准", "定位失败", "定位异常", "乱跑", "重复清扫", "漏扫"],
        "questions": [
            "是否移动过充电座位置？",
            "家中光线、镜面、落地窗或黑色地毯是否较多？",
            "传感器和雷达表面是否有灰尘或遮挡？",
        ],
        "self_check": [
            "尽量不要移动充电座；如已移动，建议重新建图。",
            "清理激光雷达、沿墙传感器、防跌落传感器表面灰尘。",
            "首次建图时打开房门，收起地面杂物和线缆。",
            "避免在强光、镜面反射、黑色高反差地面环境下建图。",
        ],
        "repair": [
            "如果持续提示雷达异常或定位模块异常，建议联系售后检测雷达组件。",
        ],
        "risk_level": "medium",
        "suggest_ticket_type": "repair",
    },
    {
        "fault_type": "weak_suction",
        "name": "吸力变小/清扫不干净",
        "keywords": ["吸力小", "吸力变小", "吸不干净", "清扫不干净", "灰尘吸不上", "毛发吸不上"],
        "questions": [
            "尘盒是否已满？",
            "滤网是否长期未清理或已潮湿？",
            "主刷、边刷是否被毛发缠绕？",
        ],
        "self_check": [
            "清空尘盒并擦干尘盒内部。",
            "清理或更换滤网，滤网潮湿时需完全晾干后再使用。",
            "清理主刷、边刷、吸口处缠绕毛发。",
            "在 APP 中调高吸力档位，地毯场景建议使用强力模式。",
        ],
        "repair": [
            "如果清理耗材后吸力仍明显不足，可能是风机异常，建议售后检测。",
        ],
        "risk_level": "low",
        "suggest_ticket_type": "repair",
    },
    {
        "fault_type": "abnormal_noise",
        "name": "噪音变大/异响",
        "keywords": ["噪音", "异响", "声音大", "刺耳", "咔咔响", "摩擦声"],
        "questions": [
            "异响来自主刷、边刷、轮子还是风机位置？",
            "是否清理过主刷和边刷缠绕物？",
            "机器是否曾跌落、进水或撞击？",
        ],
        "self_check": [
            "取下主刷、边刷检查是否有毛发、线头、硬物卡住。",
            "检查驱动轮和万向轮是否有异物。",
            "切换低吸力档位判断是否只是强力模式噪声。",
        ],
        "repair": [
            "如果清理后仍有明显异响，或伴随焦味、发热、转动异常，应停止使用并联系售后。",
        ],
        "risk_level": "medium",
        "suggest_ticket_type": "repair",
    },
    {
        "fault_type": "app_connection_failed",
        "name": "APP 无法连接/配网失败",
        "keywords": ["APP连接不上", "app连接不上", "无法连接", "配网失败", "连不上网", "WiFi连不上", "wifi连不上"],
        "questions": [
            "当前 WiFi 是否为 2.4GHz 网络？",
            "路由器名称或密码是否包含特殊字符？",
            "机器人是否处于配网模式？",
        ],
        "self_check": [
            "确认使用 2.4GHz WiFi，部分机型不支持 5GHz。",
            "将手机、机器人和路由器靠近后重新配网。",
            "重置机器人网络后重新添加设备。",
            "检查 APP 权限、蓝牙和定位权限是否开启。",
        ],
        "repair": [
            "如果多次配网失败，可以尝试更换手机热点测试；若仍失败，建议售后检测通信模块。",
        ],
        "risk_level": "low",
        "suggest_ticket_type": "repair",
    },
]


def _contains_any(text: str, words: list[str]) -> bool:
    lower = text.lower()
    return any(word.lower() in lower for word in words)


def _detect_fault(user_query: str) -> dict[str, Any]:
    scores: list[tuple[int, dict[str, Any]]] = []
    for item in FAULT_PATTERNS:
        score = 0
        for keyword in item["keywords"]:
            if keyword.lower() in user_query.lower():
                score += max(2, len(keyword))
        if score > 0:
            scores.append((score, item))

    if not scores:
        return {
            "fault_type": "general_fault",
            "name": "通用故障咨询",
            "questions": [
                "请补充机器人型号，例如 RV2001、RV3001 或 RV4001。",
                "请描述更具体的故障现象，例如不回充、不出水、异响、无法开机。",
                "故障是首次出现还是反复出现？",
            ],
            "self_check": [
                "先重启机器人和 APP。",
                "检查尘盒、水箱、主刷、边刷、轮子和传感器是否安装正常。",
                "确认设备电量充足，并清理地面线缆和障碍物。",
            ],
            "repair": [
                "如果补充具体现象后仍无法定位，建议联系人工客服或售后检测。",
            ],
            "risk_level": "unknown",
            "suggest_ticket_type": "repair",
        }

    scores.sort(key=lambda x: x[0], reverse=True)
    return scores[0][1]


def _extract_product_id(text: str) -> str | None:
    match = re.search(r"\bRV\d{4,}\b", text.upper())
    return match.group(0) if match else None


def _extract_order_id(text: str) -> str | None:
    match = re.search(r"\bO\d{8,}\b", text.upper())
    return match.group(0) if match else None


def _build_rag_summary(query: str, category: str | None = "robot_vacuum_troubleshooting") -> list[dict[str, Any]]:
    try:
        from rag.rag_service import retrieve_knowledge
    except Exception:
        return []

    try:
        chunks = retrieve_knowledge(query, category=category, top_k=3)
    except TypeError:
        chunks = retrieve_knowledge(query, top_k=3)
    except Exception:
        return []

    result = []
    for chunk in chunks[:3]:
        result.append(
            {
                "title": chunk.get("title"),
                "score": chunk.get("score"),
                "category": chunk.get("category"),
                "content": str(chunk.get("content") or "")[:260],
            }
        )
    return result


def diagnose_robot_vacuum_fault(
    query: str,
    *,
    product_id: str | None = None,
    order_id: str | None = None,
    user_has_checked: str | None = None,
    want_repair: bool | None = None,
) -> dict[str, Any]:
    query = (query or "").strip()
    product_id = product_id or _extract_product_id(query)
    order_id = order_id or _extract_order_id(query)

    fault = _detect_fault(query)
    safety_stop = _contains_any(query, SAFETY_STOP_WORDS)

    risk_level = fault.get("risk_level", "unknown")
    if safety_stop:
        risk_level = "high"

    recommend_aftersale = risk_level in {"medium", "high"} or bool(want_repair)
    suggest_ticket = recommend_aftersale or bool(order_id)

    safety_notice = None
    if safety_stop:
        safety_notice = (
            "当前描述涉及进水、电池、冒烟、烧焦味、异常发热等安全风险。"
            "建议立即停止使用，不要继续充电或自行拆机，并联系售后检测。"
        )

    return {
        "success": True,
        "query": query,
        "product_id": product_id,
        "order_id": order_id,
        "fault_type": fault.get("fault_type"),
        "fault_name": fault.get("name"),
        "risk_level": risk_level,
        "safety_stop": safety_stop,
        "safety_notice": safety_notice,
        "need_more_info": not product_id,
        "follow_up_questions": fault.get("questions", [])[:4],
        "self_check_steps": fault.get("self_check", [])[:6],
        "repair_suggestions": fault.get("repair", [])[:4],
        "recommend_aftersale": recommend_aftersale,
        "suggest_ticket": suggest_ticket,
        "suggest_ticket_type": fault.get("suggest_ticket_type", "repair"),
        "rag_chunks": _build_rag_summary(query),
        "message": "已完成扫地机器人故障诊断。",
    }
