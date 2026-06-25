from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

from agent.evidence_store import get_evidence, resolve_evidence_path
from agent.llm_client import get_llm_client, llm_enabled
from agent.memory import extract_order_id
from agent.order_screenshot_validator import validate_screenshot_against_order


ORDER_ACTIONS = [
    "查询订单详情",
    "查询物流轨迹",
    "申请退货",
    "申请换货",
    "申请维修",
    "查询退款/退货进度",
    "转人工客服审核",
]


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _guess_media_type(path: Path, fallback: str | None = None) -> str:
    if fallback:
        return fallback
    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    return "image/png"


def _json_loads_maybe(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}

    # 兼容模型输出 ```json ... ``` 或前后带说明文字的情况。
    text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.I).strip()
    text = re.sub(r"```$", "", text.strip()).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]

    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"raw_text": text}


def _extract_order_id_from_analysis(analysis: dict[str, Any], fallback_text: str = "") -> str | None:
    candidates: list[str] = []
    for key in ["order_id", "订单号", "order_no", "order_number"]:
        value = analysis.get(key)
        if value:
            candidates.append(str(value))

    for value in candidates:
        found = extract_order_id(value)
        if found:
            return found

    return extract_order_id(fallback_text)


def _call_vision_model(path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    """
    使用 OpenAI 兼容的多模态接口识别订单截图。

    默认模型为 qwen-vl-plus；如果未配置 VISION_LLM_ENABLE / DASHSCOPE_API_KEY，
    会由上层自动降级为元数据摘要，不影响普通上传流程。
    """

    if not llm_enabled() or not _env_bool("VISION_LLM_ENABLE", True):
        return {
            "success": False,
            "used_vision": False,
            "error": "视觉识别未启用，可在 .env 中设置 LLM_ENABLE=true 和 VISION_LLM_ENABLE=true。",
        }

    content = path.read_bytes()
    data_url = f"data:{_guess_media_type(path, evidence.get('content_type'))};base64,{base64.b64encode(content).decode('ascii')}"

    prompt = """
请识别这张电商订单截图中的关键信息，并只返回 JSON，不要输出多余解释。
字段要求：
{
  "order_id": "订单号，如果没有识别到则为空字符串",
  "order_status": "订单状态，例如待发货、已发货、已签收、已关闭，如果没有识别到则为空字符串",
  "product_names": ["截图中出现的商品名称"],
  "payment_amount": "支付金额或实付金额，保持原文",
  "pay_time": "支付时间，保持原文",
  "ship_time": "发货时间，保持原文",
  "receive_time": "签收时间，保持原文",
  "seller_or_shop": "店铺/商家名称，如果没有则为空字符串",
  "receiver_hint": "收货人或手机号脱敏信息，如果没有则为空字符串",
  "raw_text_summary": "用中文简要概括截图里的订单信息，不超过80字",
  "confidence": "high/medium/low"
}
注意：不要猜测截图里没有的信息，不要编造订单号。
""".strip()

    client = get_llm_client()
    completion = client.chat.completions.create(
        model=os.getenv("VISION_LLM_MODEL", "qwen-vl-plus"),
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        temperature=0.0,
        max_tokens=700,
    )
    raw = completion.choices[0].message.content or ""
    parsed = _json_loads_maybe(raw)
    parsed["success"] = True
    parsed["used_vision"] = True
    parsed["raw_model_output"] = raw
    return parsed


def _fallback_analysis(evidence: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(
        str(evidence.get(key) or "")
        for key in ["order_id", "note", "original_filename"]
    )
    order_id = evidence.get("order_id") or extract_order_id(text)
    return {
        "success": True,
        "used_vision": False,
        "order_id": order_id or "",
        "order_status": "",
        "product_names": [],
        "payment_amount": "",
        "pay_time": "",
        "ship_time": "",
        "receive_time": "",
        "seller_or_shop": "",
        "receiver_hint": "",
        "raw_text_summary": "已收到订单截图，但当前未启用视觉识别；我只能读取你填写的订单号、备注和文件名。",
        "confidence": "low",
        "error": None,
    }


def analyze_order_screenshot(evidence_id: str) -> dict[str, Any]:
    evidence = get_evidence(evidence_id)
    path = resolve_evidence_path(evidence_id)
    if not evidence or not path:
        return {
            "success": False,
            "used_vision": False,
            "evidence_id": evidence_id,
            "message": f"未找到订单截图凭证：{evidence_id}",
        }

    vision_result: dict[str, Any]
    try:
        vision_result = _call_vision_model(path, evidence)
    except Exception as exc:
        vision_result = {
            "success": False,
            "used_vision": False,
            "error": f"视觉识别失败：{type(exc).__name__}: {exc}",
        }

    if not vision_result.get("success"):
        analysis = _fallback_analysis(evidence)
        if vision_result.get("error"):
            analysis["error"] = vision_result.get("error")
    else:
        analysis = vision_result

    order_id = _extract_order_id_from_analysis(analysis, fallback_text=str(evidence.get("order_id") or ""))
    if order_id:
        analysis["order_id"] = order_id

    analysis.update(
        {
            "evidence_id": evidence_id,
            "original_filename": evidence.get("original_filename"),
            "file_url": evidence.get("file_url"),
            "created_at": evidence.get("created_at"),
            "available_actions": ORDER_ACTIONS,
        }
    )
    return analysis


def review_order_screenshot(
    *,
    evidence_ids: list[str] | None = None,
    customer_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    供 Agent 工具调用：读取最近上传的订单截图识别结果，并生成可对话化摘要。
    """

    ids = [str(x) for x in (evidence_ids or []) if x]
    if not ids:
        return {
            "success": False,
            "message": "当前对话中还没有可识别的订单截图。请先在聊天输入区上传订单截图。",
            "analyses": [],
        }

    analyses = [analyze_order_screenshot(eid) for eid in ids[:3]]
    for item in analyses:
        if item.get("success"):
            item["database_validation"] = validate_screenshot_against_order(
                item,
                customer_id=customer_id,
            )
    valid = [item for item in analyses if item.get("success")]
    if not valid:
        return {
            "success": False,
            "message": "已收到截图凭证，但暂时无法读取文件内容。你可以手动输入订单号继续处理。",
            "analyses": analyses,
        }

    first = valid[0]
    lines = ["我已经收到你上传的订单截图，并先做了信息识别："]
    lines.append(f"- 凭证 ID：{first.get('evidence_id')}")
    if first.get("used_vision"):
        lines.append("- 识别方式：视觉模型识别")
    else:
        lines.append("- 识别方式：上传元数据识别（当前未启用视觉模型或视觉识别失败）")

    order_id = first.get("order_id") or ""
    if order_id:
        lines.append(f"- 订单号：{order_id}")
    else:
        lines.append("- 订单号：未能从截图中稳定识别，请你补充订单号。")

    for label, key in [
        ("订单状态", "order_status"),
        ("支付金额", "payment_amount"),
        ("支付时间", "pay_time"),
        ("发货时间", "ship_time"),
        ("签收时间", "receive_time"),
        ("店铺/商家", "seller_or_shop"),
    ]:
        value = first.get(key)
        if value:
            lines.append(f"- {label}：{value}")

    products = first.get("product_names") or []
    if products:
        lines.append(f"- 商品：{'；'.join(str(x) for x in products[:5])}")

    if first.get("raw_text_summary"):
        lines.append(f"- 截图摘要：{first.get('raw_text_summary')}")

    validation = first.get("database_validation") or {}
    if validation:
        lines.append("")
        if validation.get("matched"):
            lines.append(f"数据库校验：{validation.get('message')}")
        elif validation.get("status") == "insufficient_fields":
            lines.append(f"数据库校验：{validation.get('message')}")
        else:
            lines.append(f"数据库校验：{validation.get('message')}")
            for mismatch in (validation.get("mismatches") or [])[:3]:
                lines.append(
                    f"- 不一致字段：{mismatch.get('field')}；截图：{mismatch.get('screenshot')}；系统：{mismatch.get('database')}"
                )
            lines.append("为避免误处理，请先确认是否上传了正确订单截图。")

    if first.get("error") and not first.get("used_vision"):
        lines.append(f"- 识别提示：{first.get('error')}")

    lines.append("")
    lines.append("接下来你想对这个订单做什么？可以直接回复：")
    lines.append("1. 查订单详情")
    lines.append("2. 查物流")
    lines.append("3. 申请退货")
    lines.append("4. 申请换货")
    lines.append("5. 申请维修")
    lines.append("6. 查退款/退货进度")

    return {
        "success": True,
        "message": "\n".join(lines),
        "analyses": analyses,
        "order_id": order_id or None,
        "primary_order_id": order_id or None,
        "customer_id": customer_id,
        "session_id": session_id,
    }
