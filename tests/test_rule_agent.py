from pprint import pprint

from agent.rule_agent import run_rule_agent


def run_case(query: str) -> None:
    print("\n" + "=" * 80)
    print(f"用户问题：{query}")
    print("-" * 80)

    state = run_rule_agent(query)

    print("识别结果：")
    pprint(
        {
            "intent": state["intent"],
            "tool_name": state["tool_name"],
            "arguments": state["arguments"],
            "error": state["error"],
        }
    )

    print("\n最终回复：")
    print(state["final_answer"])


def main() -> None:
    test_queries = [
        "帮我查一下 O202605010001 这个订单",
        "O202605010001 物流到哪了？",
        "查一下 O202605010001 的售后工单",
        "数码配件有什么退换货政策？",
        "有没有耳机商品？",
        "帮我看看 P10001 这个商品",
        "O202605010001 这个订单可以退货吗？",
        "我要申请 O202605010001 这个订单退货，原因是耳机佩戴不合适",
        "O202605020001 这个订单的扫地机器人可以维修吗？",
        "我想查物流",
        "你好",
    ]

    for query in test_queries:
        run_case(query)


if __name__ == "__main__":
    main()