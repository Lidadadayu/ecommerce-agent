from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


TEST_SESSION_ID = "TEST_CORE_PIPELINE"
TEST_USER_ID = "TEST_CORE_PIPELINE"


def ensure_memory(memory: dict[str, Any] | None) -> dict[str, Any]:
    """
    run_agent() 内部的 LangGraph / legacy agent 可能返回新的 memory，
    这个 memory 不一定包含 user_id。测试脚本必须在每轮后补回固定 user_id，
    否则下一轮 memory["user_id"] 会 KeyError。
    """

    new_memory = dict(memory or {})
    new_memory.setdefault("session_id", TEST_SESSION_ID)
    new_memory.setdefault("user_id", TEST_USER_ID)
    return new_memory


def main() -> None:
    from agent.agent import run_agent

    cases = [
        "3000以内推荐一款扫拖一体机器人",
        "扫地机器人不回充怎么办",
        "机器人有烧焦味还能继续用吗",
    ]

    memory = ensure_memory(None)

    for query in cases:
        print()
        print("=" * 80)
        print("USER:", query)

        result = run_agent(query, memory=memory, user_id=TEST_USER_ID)
        memory = ensure_memory(result.get("memory") if isinstance(result, dict) else memory)

        print("intent:", result.get("intent"))
        print("tool:", result.get("tool_name"))
        print("mode:", result.get("mode"))
        print("guard_ok:", result.get("guard_ok"))
        print("guard_issues:", json.dumps(result.get("guard_issues"), ensure_ascii=False, indent=2))
        print("context_engineering:", json.dumps(result.get("context_engineering"), ensure_ascii=False, indent=2))
        print("memory:", json.dumps(memory, ensure_ascii=False, indent=2))
        print("answer:")
        print(result.get("final_answer"))

        if not result.get("final_answer"):
            raise SystemExit("final_answer 为空")

        if "烧焦" in query:
            answer = result.get("final_answer", "")
            if not any(word in answer for word in ["停止使用", "不要继续充电", "联系售后", "售后检测"]):
                raise SystemExit("高风险问题缺少安全提醒")

    print()
    print("核心管线接入测试通过。")


if __name__ == "__main__":
    main()
