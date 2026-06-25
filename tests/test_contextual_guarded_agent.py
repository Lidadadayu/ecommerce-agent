from pprint import pprint

from agent.legacy_agent import run_contextual_guarded_agent
from agent.memory import SessionMemory


def run_case(query: str, memory: SessionMemory) -> None:
    print("\n" + "=" * 100)
    print(f"用户问题：{query}")
    print("-" * 100)

    state = run_contextual_guarded_agent(query, memory)

    # 把返回的 memory 同步回当前测试对象
    new_memory = SessionMemory.from_dict(state["memory"])
    memory.__dict__.update(new_memory.__dict__)

    print("识别与控制信息：")
    pprint(
        {
            "mode": state.get("mode"),
            "used_llm": state.get("used_llm"),
            "used_memory": state.get("used_memory"),
            "intent": state.get("intent"),
            "tool_name": state.get("tool_name"),
            "arguments": state.get("arguments"),
            "error": state.get("error"),
            "human_review": state.get("human_review"),
            "llm_error": state.get("llm_error"),
        },
        width=120,
    )

    print("\n会话记忆：")
    pprint(memory.to_dict(), width=120)

    print("\n最终回复：")
    print(state["final_answer"])


def main() -> None:
    memory = SessionMemory()

    test_queries = [
        "你好",
        "帮我查一下 O202605010001 这个订单",
        "物流到哪了？",
        "这个订单可以退货吗？",
        "我要申请退货，原因是耳机佩戴不合适",
        "查一下售后工单",
        "我想查物流",
        "O202605020001",
        "这个订单的扫地机器人可以维修吗？",
        "今天有什么新闻？",
    ]

    for query in test_queries:
        run_case(query, memory)


if __name__ == "__main__":
    main()
