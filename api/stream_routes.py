from __future__ import annotations

import asyncio
import inspect
import json
import threading
import time
import uuid
from queue import Queue
from typing import Any, Callable

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict


router = APIRouter(prefix="/api", tags=["streaming-chat"])


class StreamChatRequest(BaseModel):
    """
    流式聊天请求。

    这里不强依赖 api.schemas.ChatRequest，避免你本地 schemas.py 已经改过后产生冲突。
    """

    user_query: str
    session_id: str | None = None
    customer_id: str | None = None
    memory: dict[str, Any] | None = None

    model_config = ConfigDict(extra="ignore")


def _call_with_supported_kwargs(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        signature = inspect.signature(func)
        accepted = {key: value for key, value in kwargs.items() if key in signature.parameters}
        return func(*args, **accepted)
    except (TypeError, ValueError):
        return func(*args)


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _chunk_text(text: str, chunk_size: int = 12) -> list[str]:
    text = text or ""
    if not text:
        return []
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


def _task_status_from_memory(memory: dict[str, Any]) -> dict[str, Any]:
    context = memory.get("current_business_context") if isinstance(memory.get("current_business_context"), dict) else {}
    task = context.get("task_state") if isinstance(context.get("task_state"), dict) else {}
    if not task:
        return {
            "stage": "done",
            "title": "处理完成",
            "message": "已完成本次客服处理。",
            "progress": 1.0,
        }

    stage = str(task.get("stage") or "START")
    stage_progress = {
        "START": 0.1,
        "ORDER_IDENTIFIED": 0.28,
        "ORDER_VERIFIED": 0.42,
        "AFTERSALE_TYPE_CONFIRMED": 0.55,
        "REASON_COLLECTED": 0.66,
        "POLICY_CHECKED": 0.82,
        "USER_CONFIRMED": 0.9,
        "TICKET_CREATED": 1.0,
        "DONE": 1.0,
    }
    status = str(task.get("status") or "active")
    return {
        "stage": "done" if status == "done" else stage,
        "title": "任务状态：" + stage,
        "message": str(task.get("goal") or "正在推进多步任务。"),
        "progress": stage_progress.get(stage, 0.5),
    }


def _route_preview(user_query: str) -> dict[str, Any] | None:
    try:
        from agent.rule_router import route_user_query

        route = route_user_query(user_query)
        if isinstance(route, dict):
            return {
                "intent": route.get("intent"),
                "tool_name": route.get("tool_name"),
                "arguments": route.get("arguments") or {},
                "error": route.get("error"),
            }
    except Exception:
        return None
    return None


def _run_agent_worker(
    *,
    user_query: str,
    memory: dict[str, Any],
    user_id: str | None,
    queue: Queue,
) -> None:
    try:
        from agent.agent import run_agent

        result = _call_with_supported_kwargs(run_agent, user_query, memory=memory, user_id=user_id)
        if not isinstance(result, dict):
            result = {"final_answer": str(result), "memory": memory}
        queue.put({"type": "result", "result": result})
    except Exception as exc:
        queue.put({"type": "error", "error": f"{type(exc).__name__}: {exc}"})


async def _stream_chat_events(request: StreamChatRequest):
    user_query = (request.user_query or "").strip()
    session_id = request.session_id or f"S{uuid.uuid4().hex[:12].upper()}"
    customer_id = request.customer_id or session_id

    memory = dict(request.memory or {})
    memory.setdefault("session_id", session_id)
    memory.setdefault("customer_id", customer_id)
    memory.setdefault("user_id", customer_id)

    started = time.perf_counter()

    yield _sse(
        "connected",
        {
            "session_id": session_id,
            "customer_id": customer_id,
            "message": "已连接流式客服通道。",
        },
    )

    if not user_query:
        yield _sse("error", {"message": "请输入你的问题。"})
        yield _sse("done", {"success": False})
        return

    yield _sse(
        "status",
        {
            "stage": "received",
            "title": "收到问题",
            "message": "已收到你的问题，正在理解需求。",
            "progress": 0.08,
        },
    )
    await asyncio.sleep(0.05)

    yield _sse(
        "status",
        {
            "stage": "routing",
            "title": "识别意图",
            "message": "正在判断是选购、订单、物流、故障还是售后问题。",
            "progress": 0.16,
        },
    )

    route = _route_preview(user_query)
    if route:
        yield _sse(
            "route",
            {
                "intent": route.get("intent"),
                "tool_name": route.get("tool_name"),
                "message": "已完成意图识别。",
                "progress": 0.24,
            },
        )

        if route.get("tool_name"):
            yield _sse(
                "tool_start",
                {
                    "tool_name": route.get("tool_name"),
                    "message": "正在调用业务工具或知识库。",
                    "progress": 0.34,
                },
            )
    else:
        yield _sse(
            "status",
            {
                "stage": "routing",
                "title": "识别意图",
                "message": "已进入 Agent 自动处理流程。",
                "progress": 0.24,
            },
        )

    queue: Queue = Queue()
    worker = threading.Thread(
        target=_run_agent_worker,
        kwargs={
            "user_query": user_query,
            "memory": memory,
            "user_id": customer_id,
            "queue": queue,
        },
        daemon=True,
    )
    worker.start()

    heartbeat_messages = [
        "正在查询业务数据并整理回答。",
        "正在检索知识库和工具结果。",
        "正在进行安全与防幻觉检查。",
        "正在生成最终客服回复。",
    ]
    heartbeat_index = 0

    while worker.is_alive():
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        msg = heartbeat_messages[heartbeat_index % len(heartbeat_messages)]
        heartbeat_index += 1

        yield _sse(
            "status",
            {
                "stage": "processing",
                "title": "处理中",
                "message": msg,
                "elapsed_ms": elapsed,
                "progress": min(0.82, 0.42 + heartbeat_index * 0.06),
            },
        )
        await asyncio.sleep(0.75)

    item = queue.get() if not queue.empty() else {"type": "error", "error": "Agent 未返回结果。"}

    if item.get("type") == "error":
        yield _sse(
            "error",
            {
                "message": item.get("error") or "Agent 处理失败。",
                "progress": 1.0,
            },
        )
        yield _sse("done", {"success": False, "session_id": session_id})
        return

    result = item.get("result") or {}
    answer = str(result.get("final_answer") or "系统没有返回回答。")

    yield _sse(
        "status",
        {
            "stage": "answering",
            "title": "生成回复",
            "message": "已完成业务处理，正在输出回答。",
            "progress": 0.88,
        },
    )

    for chunk in _chunk_text(answer, chunk_size=10 if len(answer) < 800 else 18):
        yield _sse("answer_delta", {"content": chunk})
        await asyncio.sleep(0.018 if len(answer) < 800 else 0.008)

    final_memory = result.get("memory") if isinstance(result.get("memory"), dict) else memory
    final_memory.setdefault("session_id", session_id)
    final_memory.setdefault("customer_id", customer_id)
    final_memory.setdefault("user_id", customer_id)

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

    yield _sse(
        "final",
        {
            "success": True,
            "session_id": session_id,
            "customer_id": customer_id,
            "final_answer": answer,
            "memory": final_memory,
            "intent": result.get("intent"),
            "tool_name": result.get("tool_name"),
            "mode": result.get("mode"),
            "elapsed_ms": result.get("elapsed_ms") or elapsed_ms,
            "guard_ok": result.get("guard_ok"),
            "guard_issues": result.get("guard_issues") or [],
            "task_status": _task_status_from_memory(final_memory),
        },
    )
    yield _sse("done", {"success": True, "session_id": session_id, "elapsed_ms": elapsed_ms})


@router.post("/chat/stream")
async def chat_stream(request: StreamChatRequest) -> StreamingResponse:
    """
    真正的后端 SSE 流式输出接口。

    注意：
    - 这是后端 StreamingResponse，不是前端假流式。
    - 当前 Agent 内部仍可能是阻塞式工具链，所以本接口会先流式输出状态事件和心跳。
    - Agent 返回 final_answer 后，再通过 answer_delta 持续输出回答文本。
    """

    return StreamingResponse(
        _stream_chat_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
