from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SYSTEM_PROMPT = """
你是一个电商售后与运营 Agent 助手，负责商品咨询、订单查询、物流跟踪、退换货规则解释、售后工单处理和运营数据问答。
边界规则：不要回答新闻、投资、医疗、法律、政治等非电商业务问题；不要编造订单、物流、商品、工单、退款或赔付信息；工具结果优先；只能做售后资格预判断、解释规则、生成工单或提示人工审核，不能直接决定最终退货、退款、赔付或维修结论。
回复风格：礼貌、自然、简洁清楚。
"""


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def llm_enabled() -> bool:
    return _env_bool("LLM_ENABLE", True)


def get_llm_model() -> str:
    return os.getenv("LLM_MODEL", "qwen-plus")


def get_llm_client():
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not set. Please configure it in your .env file.")
    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError("openai package is not installed. Please run: pip install openai") from exc

    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        timeout=_env_float("LLM_TIMEOUT_SECONDS", 15.0),
        max_retries=0,
    )


def chat_with_llm(user_query: str, system_prompt: str = SYSTEM_PROMPT, temperature: float = 0.3, max_tokens: int = 800, fallback_content: str | None = None) -> dict[str, Any]:
    fallback = fallback_content or "抱歉，我现在暂时无法连接大模型服务。你可以继续查询订单、物流、商品或售后信息。"
    if not llm_enabled():
        return {"success": False, "content": fallback, "error": "LLM is disabled by LLM_ENABLE=false.", "attempts": 0}
    attempts = max(0, _env_int("LLM_MAX_RETRIES", 1)) + 1
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            client = get_llm_client()
            completion = client.chat.completions.create(
                model=get_llm_model(),
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_query}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return {"success": True, "content": completion.choices[0].message.content or fallback, "error": None, "attempts": attempt}
        except Exception as exc:
            last_error = str(exc)
            if attempt < attempts:
                time.sleep(0.5)
    return {"success": False, "content": fallback, "error": last_error, "attempts": attempts}


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        return str(value)


def rewrite_tool_answer(user_query: str, intent: str, tool_name: str, arguments: dict[str, Any], tool_result: dict[str, Any], template_answer: str, human_review: dict[str, Any] | None = None, temperature: float = 0.2, max_tokens: int = 900) -> dict[str, Any]:
    prompt = f"""
用户问题：{user_query}
系统识别意图：{intent}
调用工具：{tool_name}
工具参数：{_json_text(arguments)}
工具原始结果：{_json_text(tool_result)}
人工审核判断：{_json_text(human_review)}
当前模板回复：{template_answer}

请把“当前模板回复”改写成更自然的客服回复。必须严格基于工具结果，不要编造数据；订单号、商品 ID、工单号、物流状态、售后判断结论不能改；如果 requires_human_review=True，必须提示需要人工客服进一步审核。
"""
    return chat_with_llm(prompt, system_prompt=SYSTEM_PROMPT, temperature=temperature, max_tokens=max_tokens, fallback_content=template_answer)
