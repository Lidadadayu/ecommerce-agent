from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any


def _request_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json"}

    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")

    return json.loads(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="测试 Ecommerce Agent API 是否可用。")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    print("1. Health")
    health = _request_json(f"{base_url}/api/health")
    print(json.dumps(health, ensure_ascii=False, indent=2))

    print("\n2. Domain")
    domain = _request_json(f"{base_url}/api/domain")
    print(json.dumps(domain, ensure_ascii=False, indent=2)[:1200])

    print("\n3. Chat")
    memory = None
    session_id = None

    queries = [
        "3000以内推荐一款扫拖一体机器人",
        "对比 RV2001 和 RV4001",
        "扫地机器人不回充怎么办",
    ]

    for query in queries:
        payload = {
            "user_query": query,
            "memory": memory,
            "session_id": session_id,
        }
        result = _request_json(f"{base_url}/api/chat", method="POST", payload=payload)
        memory = result.get("memory")
        session_id = result.get("session_id")

        print("\nUser:", query)
        print("Intent:", result.get("intent"))
        print("Tool:", result.get("tool_name"))
        print("Mode:", result.get("mode"))
        print("Answer:", str(result.get("final_answer") or "")[:500])


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        print(f"API 请求失败：{exc}")
        print("请先运行：python scripts/run_api.py")
        raise SystemExit(1)
