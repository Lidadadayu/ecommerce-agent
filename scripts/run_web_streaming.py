from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="启动带后端 SSE 流式输出的前端。")
    parser.add_argument("--api-base-url", default=os.getenv("AGENT_API_BASE_URL", "http://127.0.0.1:8001"))
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--dev-mode", action="store_true")
    args = parser.parse_args()

    env = os.environ.copy()
    env["AGENT_API_BASE_URL"] = args.api_base_url
    env["FRONTEND_DEV_MODE"] = "1" if args.dev_mode else "0"

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(PROJECT_ROOT / "app_api_streaming.py"),
        "--server.port",
        str(args.port),
        "--server.address",
        "127.0.0.1",
    ]

    print("启动流式前端：", " ".join(cmd))
    print("API 地址：", args.api_base_url)
    subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=False)


if __name__ == "__main__":
    main()
