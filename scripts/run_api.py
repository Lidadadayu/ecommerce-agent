from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="启动 Ecommerce Agent API 服务。默认已包含 /api/chat/stream 流式接口。"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "api.server:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]

    if args.reload:
        cmd.append("--reload")

    print("启动 Agent API：", " ".join(cmd))
    print(f"API 文档：http://{args.host}:{args.port}/docs")
    print(f"流式接口：POST http://{args.host}:{args.port}/api/chat/stream")
    raise SystemExit(subprocess.call(cmd, cwd=str(PROJECT_ROOT)))


if __name__ == "__main__":
    main()
