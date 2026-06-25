from __future__ import annotations

from typing import Any

from agent.answer_guard import guard_answer
from agent.context_builder import build_prompt_context, render_chat_messages, render_prompt_text
from agent.long_term_memory import build_user_profile_text, update_long_term_memory_from_text


def finalize_answer_with_core_engineering(
    *,
    user_query: str,
    draft_answer: str,
    route: dict[str, Any] | None = None,
    tool_result: dict[str, Any] | None = None,
    memory: dict[str, Any] | None = None,
    user_id: str | None = None,
    update_long_term_memory: bool = False,
) -> dict[str, Any]:
    """
    核心回答后处理管线。

    当前作用：
    1. 构建标准 PromptContext；
    2. 生成可用于 LLM 的上下文 prompt；
    3. 对草稿回答做 answer_guard 检查；
    4. 必要时修复越权承诺/安全风险；
    5. 可选更新长期记忆。

    该函数可以在 rule_agent 或 LangGraph 的 final node 中调用。
    """

    if user_id and update_long_term_memory:
        update_long_term_memory_from_text(user_id=user_id, text=user_query)

    if user_id:
        profile_text = build_user_profile_text(user_id)
        if profile_text:
            memory = dict(memory or {})
            profile = dict(memory.get("user_profile") or {})
            profile["long_term_profile_text"] = profile_text
            memory["user_profile"] = profile

    context = build_prompt_context(
        user_query=user_query,
        route=route,
        tool_result=tool_result,
        memory=memory,
        draft_answer=draft_answer,
    )

    guard_result = guard_answer(draft_answer, context)
    final_answer = guard_result.repaired_answer or draft_answer

    return {
        "final_answer": final_answer,
        "guard_ok": guard_result.ok,
        "guard_issues": [
            {
                "code": issue.code,
                "severity": issue.severity,
                "message": issue.message,
                "suggestion": issue.suggestion,
            }
            for issue in guard_result.issues
        ],
        "prompt_text": render_prompt_text(context),
        "prompt_messages": render_chat_messages(context),
        "context": context,
    }
