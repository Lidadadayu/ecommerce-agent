from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUEUE_DIR = PROJECT_ROOT / "data" / "review_queue"
DEFAULT_QUEUE_FILE = DEFAULT_QUEUE_DIR / "human_review_tasks.json"


REVIEW_TRUE_KEYS = {
    "required",
    "require_review",
    "requires_review",
    "need_review",
    "needs_review",
    "need_human_review",
    "human_review_required",
    "should_review",
    "should_human_review",
}


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _new_review_id() -> str:
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"HR{now}{suffix}"


def _safe_text(value: Any, max_len: int = 500) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _safe_json_obj(value: Any, max_text_len: int = 1200) -> Any:
    """
    避免人工审核队列写入过大的对象。
    """

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value if not isinstance(value, str) else _safe_text(value, max_text_len)

    if isinstance(value, list):
        return [_safe_json_obj(item, max_text_len=max_text_len) for item in value[:20]]

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:80]:
            result[str(key)] = _safe_json_obj(item, max_text_len=max_text_len)
        return result

    return _safe_text(value, max_text_len)


def _load_tasks(queue_file: Path = DEFAULT_QUEUE_FILE) -> list[dict[str, Any]]:
    if not queue_file.exists():
        return []

    try:
        data = json.loads(queue_file.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    return []


def _save_tasks(tasks: list[dict[str, Any]], queue_file: Path = DEFAULT_QUEUE_FILE) -> None:
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def is_human_review_required(human_review: dict[str, Any] | None) -> bool:
    """
    兼容不同 human_review.py 的返回格式。

    只要出现以下语义，就认为需要进入人工审核队列：
    - require_review / required / human_review_required 等布尔字段为 True
    - status 为 required / pending / need_review
    - action 为 human_review / manual_review / transfer_to_human
    - risk_level 为 high / critical
    """

    if not isinstance(human_review, dict) or not human_review:
        return False

    for key in REVIEW_TRUE_KEYS:
        if bool(human_review.get(key)):
            return True

    status = str(human_review.get("status") or "").lower()
    if status in {"required", "pending", "need_review", "needs_review", "manual_review"}:
        return True

    action = str(human_review.get("action") or "").lower()
    if action in {"human_review", "manual_review", "transfer_to_human", "handoff"}:
        return True

    risk_level = str(human_review.get("risk_level") or human_review.get("level") or "").lower()
    if risk_level in {"high", "critical", "severe"}:
        return True

    return False


def _extract_reasons(human_review: dict[str, Any] | None) -> list[str]:
    if not isinstance(human_review, dict):
        return []

    reason_fields = [
        "reason",
        "reasons",
        "risk_reason",
        "risk_reasons",
        "review_reason",
        "message",
    ]

    reasons: list[str] = []

    for field in reason_fields:
        value = human_review.get(field)

        if isinstance(value, str) and value.strip():
            reasons.append(value.strip())

        elif isinstance(value, list):
            for item in value:
                text = _safe_text(item, 160)
                if text:
                    reasons.append(text)

    # 去重
    seen = set()
    return [x for x in reasons if not (x in seen or seen.add(x))]


def create_human_review_task(
    *,
    user_query: str,
    intent: str | None,
    tool_name: str | None,
    arguments: dict[str, Any] | None,
    tool_result: dict[str, Any] | None,
    human_review: dict[str, Any] | None,
    memory: dict[str, Any] | None = None,
    final_answer: str | None = None,
    queue_file: Path = DEFAULT_QUEUE_FILE,
) -> dict[str, Any] | None:
    """
    创建人工审核任务。

    返回 None 表示当前不需要人工审核。
    """

    if not is_human_review_required(human_review):
        return None

    tasks = _load_tasks(queue_file)

    review_id = _new_review_id()

    memory = memory or {}
    current_context = memory.get("current_business_context") if isinstance(memory, dict) else {}

    task = {
        "review_id": review_id,
        "status": "pending",
        "created_at": _now_text(),
        "updated_at": _now_text(),
        "intent": intent,
        "tool_name": tool_name,
        "risk_level": (human_review or {}).get("risk_level") or (human_review or {}).get("level") or "unknown",
        "reasons": _extract_reasons(human_review),
        "user_query": _safe_text(user_query, 500),
        "arguments": _safe_json_obj(arguments or {}),
        "tool_result": _safe_json_obj(tool_result or {}),
        "human_review": _safe_json_obj(human_review or {}),
        "memory_context": _safe_json_obj(current_context or {}),
        "final_answer": _safe_text(final_answer, 800),
        "reviewer": None,
        "review_comment": None,
        "decision": None,
    }

    tasks.append(task)
    _save_tasks(tasks, queue_file)

    return task


def list_human_review_tasks(
    *,
    status: str | None = None,
    limit: int = 50,
    queue_file: Path = DEFAULT_QUEUE_FILE,
) -> list[dict[str, Any]]:
    tasks = _load_tasks(queue_file)

    if status:
        tasks = [task for task in tasks if task.get("status") == status]

    tasks.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return tasks[:limit]


def get_human_review_task(
    review_id: str,
    *,
    queue_file: Path = DEFAULT_QUEUE_FILE,
) -> dict[str, Any] | None:
    tasks = _load_tasks(queue_file)
    for task in tasks:
        if task.get("review_id") == review_id:
            return task
    return None


def update_human_review_task(
    review_id: str,
    *,
    status: str,
    reviewer: str | None = None,
    decision: str | None = None,
    comment: str | None = None,
    queue_file: Path = DEFAULT_QUEUE_FILE,
) -> dict[str, Any] | None:
    tasks = _load_tasks(queue_file)

    for task in tasks:
        if task.get("review_id") != review_id:
            continue

        task["status"] = status
        task["updated_at"] = _now_text()

        if reviewer is not None:
            task["reviewer"] = reviewer

        if decision is not None:
            task["decision"] = decision

        if comment is not None:
            task["review_comment"] = comment

        _save_tasks(tasks, queue_file)
        return task

    return None


def format_human_review_task_notice(task: dict[str, Any] | None) -> str:
    if not task:
        return ""

    review_id = task.get("review_id")
    if not review_id:
        return ""

    return (
        "\n\n人工审核记录已生成："
        f"{review_id}。后续人工客服可根据该编号查看订单、售后原因、工具结果和风险说明。"
    )
