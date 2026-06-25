from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="测试 /api/chat/stream SSE 接口。")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--query", default="扫地机器人不回充怎么办")
    parser.add_argument("--customer-id", default="C10001")
    args = parser.parse_args()

    from frontend_stream_client import AgentStreamClient, AgentStreamError

    client = AgentStreamClient(args.api_base_url)

    final_answer = ""
    seen_events: list[str] = []

    try:
        stream = client.stream_chat(
            args.query,
            customer_id=args.customer_id,
            memory={"customer_id": args.customer_id, "user_id": args.customer_id},
        )

        for event in stream:
            seen_events.append(event.get("event", ""))
            print(json.dumps(event, ensure_ascii=False))

            if event.get("event") == "answer_delta":
                final_answer += event.get("content", "")

    except AgentStreamError as exc:
        msg = str(exc)
        if "404" in msg:
            print("流式接口返回 404。请确认你已经应用入口统一补丁，并使用：")
            print("  python scripts/run_api.py --port 8001")
            print("或：")
            print("  python scripts/run_system.py")
            print("然后在 http://127.0.0.1:8001/docs 中检查 POST /api/chat/stream 是否存在。")
        raise

    if not final_answer:
        raise SystemExit("没有收到 answer_delta。")

    if "done" not in seen_events:
        raise SystemExit("没有收到 done 事件。")

    print()
    print("流式接口测试通过。")
    print("final_answer preview:", final_answer[:160])


if __name__ == "__main__":
    main()
