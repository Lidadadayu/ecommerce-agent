from __future__ import annotations

import inspect
import time
from typing import Any


def _call_with_supported_kwargs(func, *args, **kwargs):
    """
    兼容不同版本函数签名。

    你的项目经过多轮迭代，部分函数可能是：
        run_graph_agent(user_query)
    也可能是：
        run_graph_agent(user_query, memory=memory)

    这里根据函数签名只传它支持的参数，避免 TypeError。
    """

    try:
        signature = inspect.signature(func)
        accepted = {
            key: value
            for key, value in kwargs.items()
            if key in signature.parameters
        }
        return func(*args, **accepted)
    except (TypeError, ValueError):
        # 某些可调用对象没有标准签名，退回最简单调用。
        return func(*args)


def _normalize_agent_result(
    result: Any,
    *,
    user_query: str,
    memory: dict[str, Any] | None = None,
    mode: str = "unknown",
    graph_error: str | None = None,
) -> dict[str, Any]:
    if isinstance(result, dict):
        state = dict(result)
    else:
        state = {"final_answer": str(result)}

    state.setdefault("user_query", user_query)
    state.setdefault("memory", memory or {})
    state.setdefault("mode", mode)

    if graph_error:
        state["graph_error"] = graph_error

    # 兼容 route 字段缺失的情况。
    if "route" not in state:
        state["route"] = {
            "intent": state.get("intent"),
            "tool_name": state.get("tool_name"),
            "arguments": state.get("arguments") or {},
            "error": state.get("error"),
        }

    # 兼容顶层字段缺失的情况，便于 API 和前端展示。
    route = state.get("route") or {}
    state.setdefault("intent", route.get("intent"))
    state.setdefault("tool_name", route.get("tool_name"))
    state.setdefault("arguments", route.get("arguments") or {})

    final_answer = state.get("final_answer")
    if final_answer is None:
        final_answer = state.get("answer") or state.get("response") or ""
    state["final_answer"] = str(final_answer)

    return state


def _run_graph(user_query: str, memory: dict[str, Any] | None = None) -> dict[str, Any]:
    from agent.workflow import run_graph_agent

    result = _call_with_supported_kwargs(run_graph_agent, user_query, memory=memory)
    return _normalize_agent_result(
        result,
        user_query=user_query,
        memory=memory,
        mode="langgraph_multi_agent_orchestration",
    )


def _run_fallback(user_query: str, memory: dict[str, Any] | None = None, graph_error: str | None = None) -> dict[str, Any]:
    """
    LangGraph 失败时的兜底链路。

    优先使用 legacy_agent，其次使用 rule_agent。
    """

    try:
        from agent.legacy_agent import run_contextual_guarded_agent

        result = _call_with_supported_kwargs(run_contextual_guarded_agent, user_query, memory=memory)
        return _normalize_agent_result(
            result,
            user_query=user_query,
            memory=memory,
            mode="legacy_contextual_guarded_agent",
            graph_error=graph_error,
        )
    except Exception as legacy_exc:
        from agent.rule_agent import run_rule_agent

        result = run_rule_agent(user_query)
        state = _normalize_agent_result(
            result,
            user_query=user_query,
            memory=memory,
            mode="rule_agent_fallback",
            graph_error=graph_error,
        )
        state["legacy_error"] = f"{type(legacy_exc).__name__}: {legacy_exc}"
        return state


def _apply_core_pipeline(
    state: dict[str, Any],
    *,
    user_query: str,
    memory: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    接入核心工程能力：
    1. 标准 PromptContext；
    2. Answer Guard 防幻觉；
    3. 可选长期记忆；
    4. 保留 guard 结果用于日志和前端调试。
    """

    try:
        from agent.core_pipeline import finalize_answer_with_core_engineering

        route = state.get("route") or {
            "intent": state.get("intent"),
            "tool_name": state.get("tool_name"),
            "arguments": state.get("arguments") or {},
            "error": state.get("error"),
        }

        tool_result = state.get("tool_result")

        # 如果没有完整 tool_result，但有工具调用失败/成功信息，也尽量构造一个简化结果。
        if tool_result is None and state.get("tool_name"):
            tool_result = {
                "success": bool(state.get("tool_success", True)),
                "tool_name": state.get("tool_name"),
                "message": str(state.get("tool_message") or ""),
                "result": state.get("tool_data") if isinstance(state.get("tool_data"), dict) else None,
            }

        core = finalize_answer_with_core_engineering(
            user_query=user_query,
            draft_answer=state.get("final_answer", ""),
            route=route,
            tool_result=tool_result,
            memory=state.get("memory") or memory or {},
            user_id=user_id,
            update_long_term_memory=bool(user_id),
        )

        state["final_answer"] = core["final_answer"]
        state["guard_ok"] = core["guard_ok"]
        state["guard_issues"] = core["guard_issues"]

        # 不把完整 prompt 全量返回前端，避免页面太乱，也避免暴露过多内部上下文。
        prompt_text = core.get("prompt_text") or ""
        state["context_engineering"] = {
            "enabled": True,
            "prompt_preview": prompt_text[:600],
            "prompt_chars": len(prompt_text),
            "evidence_count": len(getattr(core.get("context"), "evidences", []) or []),
        }

    except Exception as exc:
        # 核心后处理不能影响主业务回答。
        state["guard_ok"] = False
        state["guard_issues"] = [
            {
                "code": "core_pipeline_error",
                "severity": "medium",
                "message": f"{type(exc).__name__}: {exc}",
                "suggestion": "检查 agent/core_pipeline.py、context_builder.py、answer_guard.py 是否存在导入或数据结构问题。",
            }
        ]
        state["context_engineering"] = {"enabled": False, "error": f"{type(exc).__name__}: {exc}"}

    return state


def _log_run_safely(state: dict[str, Any], *, user_query: str, elapsed_ms: float) -> None:
    try:
        from agent.run_logger import log_agent_run

        # 兼容不同版本 log_agent_run 签名。
        _call_with_supported_kwargs(
            log_agent_run,
            user_query=user_query,
            result=state,
            elapsed_ms=elapsed_ms,
        )
    except Exception:
        # 日志失败不影响用户请求。
        pass


def run_agent(
    user_query: str,
    memory: dict[str, Any] | None = None,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Agent 统一入口。

    当前主链路：
        FastAPI / Streamlit
        ↓
        run_agent()
        ↓
        LangGraph 多节点编排
        ↓
        工具 / RAG / 记忆 / 人工审核
        ↓
        Core Pipeline：Context Builder + Answer Guard + Long-term Memory
        ↓
        运行日志
        ↓
        返回前端

    说明：
    - LangGraph 失败时自动 fallback 到 legacy/rule agent。
    - Core Pipeline 失败不会中断业务回答，只会记录 guard_issues。
    """

    start = time.perf_counter()
    query = (user_query or "").strip()

    if not query:
        return {
            "user_query": user_query,
            "final_answer": "请输入你的问题，例如商品推荐、订单查询、物流查询或售后申请。",
            "memory": memory or {},
            "intent": "unknown",
            "tool_name": None,
            "mode": "empty_query",
            "guard_ok": True,
            "guard_issues": [],
        }

    safe_memory = dict(memory or {})
    if user_id:
        safe_memory.setdefault("user_id", user_id)

    try:
        state = _run_graph(query, memory=safe_memory)
    except Exception as graph_exc:
        state = _run_fallback(
            query,
            memory=safe_memory,
            graph_error=f"{type(graph_exc).__name__}: {graph_exc}",
        )

    state = _normalize_agent_result(
        state,
        user_query=query,
        memory=safe_memory,
        mode=state.get("mode") or "unknown",
        graph_error=state.get("graph_error"),
    )

    # 使用 session_id/user_id 作为长期记忆 key。没有 user_id 时不启用长期记忆写入。
    effective_user_id = user_id or safe_memory.get("user_id")

    state = _apply_core_pipeline(
        state,
        user_query=query,
        memory=safe_memory,
        user_id=effective_user_id,
    )

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    state["elapsed_ms"] = elapsed_ms

    _log_run_safely(state, user_query=query, elapsed_ms=elapsed_ms)

    return state
