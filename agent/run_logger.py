from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "data" / "runtime" / "conversation_logs"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def _new_run_id() -> str:
    return f"RUN{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"


def _safe_text(value: Any, max_len: int = 1200) -> str:
    if value is None:
        return ""

    text = str(value).replace("\r", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "..."

    return text


def _safe_json(value: Any, max_len: int = 1500, max_items: int = 40) -> Any:
    """
    将运行状态压缩成适合写入日志的 JSON。
    避免把大模型长回复、完整工具结果或超大记忆无限写入日志。
    """

    if value is None:
        return None

    if isinstance(value, (int, float, bool)):
        return value

    if isinstance(value, str):
        return _safe_text(value, max_len)

    if isinstance(value, list):
        return [_safe_json(item, max_len=max_len, max_items=max_items) for item in value[:max_items]]

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:max_items]:
            result[str(key)] = _safe_json(item, max_len=max_len, max_items=max_items)
        return result

    return _safe_text(value, max_len)


def _extract_memory_brief(memory: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(memory, dict):
        return {}

    pending = memory.get("pending_action")
    if not isinstance(pending, dict):
        pending = None

    return {
        "current_order_id": memory.get("current_order_id"),
        "current_product_id": memory.get("current_product_id"),
        "current_ticket_id": memory.get("current_ticket_id"),
        "last_intent": memory.get("last_intent"),
        "last_tool_name": memory.get("last_tool_name"),
        "pending_action": pending,
        "current_business_context": memory.get("current_business_context"),
    }


def _extract_tool_result_brief(tool_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(tool_result, dict):
        return None

    result = tool_result.get("result")
    success = tool_result.get("success")
    error = tool_result.get("error")
    tool_name = tool_result.get("tool_name")

    if isinstance(result, dict):
        brief = {
            "success": result.get("success", success),
            "message": result.get("message"),
            "count": result.get("count"),
        }

        for key in ["order_id", "product_id", "ticket_id", "review_id", "status"]:
            if key in result:
                brief[key] = result.get(key)

        # 商品推荐和 RAG 结果只保留摘要
        if isinstance(result.get("products"), list):
            brief["products"] = [
                {
                    "product_id": item.get("product_id"),
                    "name": item.get("name"),
                    "price": item.get("price"),
                    "_match_score": item.get("_match_score"),
                }
                for item in result.get("products", [])[:5]
                if isinstance(item, dict)
            ]

        if isinstance(result.get("chunks"), list):
            brief["chunks"] = [
                {
                    "title": item.get("title"),
                    "score": item.get("score"),
                    "category": item.get("category"),
                }
                for item in result.get("chunks", [])[:5]
                if isinstance(item, dict)
            ]

        return {
            "tool_name": tool_name,
            "success": success,
            "error": error,
            "result": _safe_json(brief),
        }

    return _safe_json(tool_result)


def build_run_record(
    *,
    user_query: str,
    input_memory: dict[str, Any] | None,
    result: dict[str, Any] | None,
    elapsed_ms: float,
    error: str | None = None,
) -> dict[str, Any]:
    result = result or {}
    route = result.get("route") if isinstance(result.get("route"), dict) else {}

    memory = result.get("memory")
    if not isinstance(memory, dict):
        memory = input_memory if isinstance(input_memory, dict) else {}

    record = {
        "run_id": _new_run_id(),
        "created_at": _now(),
        "elapsed_ms": round(float(elapsed_ms), 2),
        "user_query": _safe_text(user_query, 800),
        "mode": result.get("mode"),
        "used_llm": result.get("used_llm"),
        "intent": result.get("intent") or route.get("intent") or result.get("last_intent"),
        "tool_name": result.get("tool_name") or route.get("tool_name") or result.get("last_tool_name"),
        "arguments": _safe_json(result.get("arguments") or route.get("arguments") or {}),
        "tool_result": _extract_tool_result_brief(result.get("tool_result")),
        "human_review": _safe_json(result.get("human_review")),
        "human_review_task": _safe_json(result.get("human_review_task")),
        "graph_error": result.get("graph_error"),
        "llm_error": result.get("llm_error"),
        "error": error,
        "memory_brief": _extract_memory_brief(memory),
        "final_answer_preview": _safe_text(result.get("final_answer"), 1000),
    }

    return record


def append_agent_run_log(
    *,
    user_query: str,
    input_memory: dict[str, Any] | None,
    result: dict[str, Any] | None,
    elapsed_ms: float,
    error: str | None = None,
) -> dict[str, Any]:
    """
    将每次 Agent 调用写入 JSONL 日志。

    日志位置：
        data/runtime/conversation_logs/agent_runs_YYYYMMDD.jsonl
    """

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"agent_runs_{_today()}.jsonl"

    record = build_run_record(
        user_query=user_query,
        input_memory=input_memory,
        result=result,
        elapsed_ms=elapsed_ms,
        error=error,
    )

    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def load_run_logs(
    *,
    date_text: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    date_text = date_text or _today()
    log_file = LOG_DIR / f"agent_runs_{date_text}.jsonl"

    if not log_file.exists():
        return []

    records: list[dict[str, Any]] = []
    with log_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    records.append(item)
            except Exception:
                continue

    return records[-limit:]


def summarize_logs(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "total": 0,
            "intent_count": {},
            "tool_count": {},
            "mode_count": {},
            "avg_elapsed_ms": 0,
            "error_count": 0,
        }

    intent_count: dict[str, int] = {}
    tool_count: dict[str, int] = {}
    mode_count: dict[str, int] = {}
    error_count = 0
    elapsed_total = 0.0

    for item in records:
        intent = str(item.get("intent") or "unknown")
        tool = str(item.get("tool_name") or "none")
        mode = str(item.get("mode") or "unknown")

        intent_count[intent] = intent_count.get(intent, 0) + 1
        tool_count[tool] = tool_count.get(tool, 0) + 1
        mode_count[mode] = mode_count.get(mode, 0) + 1

        if item.get("error") or item.get("graph_error") or item.get("llm_error"):
            error_count += 1

        try:
            elapsed_total += float(item.get("elapsed_ms") or 0)
        except Exception:
            pass

    return {
        "total": len(records),
        "intent_count": dict(sorted(intent_count.items(), key=lambda x: x[1], reverse=True)),
        "tool_count": dict(sorted(tool_count.items(), key=lambda x: x[1], reverse=True)),
        "mode_count": dict(sorted(mode_count.items(), key=lambda x: x[1], reverse=True)),
        "avg_elapsed_ms": round(elapsed_total / len(records), 2),
        "error_count": error_count,
    }


def log_agent_run(
    *,
    user_query: str,
    result: dict[str, Any] | None,
    elapsed_ms: float,
    input_memory: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """
    兼容 agent.agent._log_run_safely 中使用的历史函数名。

    旧代码调用 log_agent_run，新日志模块实际实现为 append_agent_run_log。
    保留该别名后，Agent 主流程日志可以正常写入，同时不影响已有调用方。
    """

    if input_memory is None and isinstance(result, dict):
        memory = result.get("memory")
        input_memory = memory if isinstance(memory, dict) else None

    return append_agent_run_log(
        user_query=user_query,
        input_memory=input_memory,
        result=result,
        elapsed_ms=elapsed_ms,
        error=error,
    )
