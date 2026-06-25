from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEMO_QUERIES = [
    "你是谁？",
    "养宠家庭怎么选扫地机器人？",
    "3000以内推荐一款扫拖一体机器人",
    "RV4001 参数怎么样",
    "对比 RV2001 和 RV4001",
    "扫地机器人不回充怎么办",
    "扫拖一体机器人拖地不出水怎么办",
    "边刷多久换一次？",
]


def main() -> None:
    from agent.agent import run_agent
    from agent.domain_loader import get_active_domain_config

    domain = get_active_domain_config()
    print("=" * 80)
    print("Quick Demo")
    print(f"当前领域：{domain.domain_id} / {domain.domain_name}")
    print("=" * 80)

    memory = None

    for idx, query in enumerate(DEMO_QUERIES, start=1):
        print()
        print("-" * 80)
        print(f"[User {idx}] {query}")
        print("-" * 80)

        result = run_agent(query, memory=memory)
        memory = result.get("memory") if isinstance(result, dict) else None

        answer = result.get("final_answer") if isinstance(result, dict) else str(result)
        print(answer)


if __name__ == "__main__":
    main()
