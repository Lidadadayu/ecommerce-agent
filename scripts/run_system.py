from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) != 0


def find_available_port(host: str, preferred: int, max_try: int = 30) -> int:
    for port in range(preferred, preferred + max_try):
        if is_port_available(host, port):
            return port
    raise RuntimeError(f"从 {preferred} 开始连续 {max_try} 个端口都被占用。")


def wait_for_api(host: str, port: int, timeout_sec: int = 45) -> bool:
    url = f"http://{host}:{port}/api/health"
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            time.sleep(1)
    return False


def start_process(name: str, cmd: list[str], env: dict[str, str]) -> subprocess.Popen:
    print()
    print("=" * 80)
    print(f"启动{name}")
    print("=" * 80)
    print(" ".join(cmd))
    return subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), env=env)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="一键启动最终版系统：FastAPI 后端 + SSE 流式接口 + Streamlit 用户前端。"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=8001)
    parser.add_argument("--web-port", type=int, default=8501)
    parser.add_argument("--auto-port", action="store_true", help="端口被占用时自动寻找可用端口")
    parser.add_argument("--reload", action="store_true", help="后端开启 uvicorn --reload")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--dev-mode", action="store_true", help="前端显示开发调试面板")
    args = parser.parse_args()

    host = args.host
    api_port = args.api_port
    web_port = args.web_port

    if args.auto_port:
        api_port = find_available_port(host, api_port)
        web_port = find_available_port("127.0.0.1", web_port)
    else:
        if not is_port_available(host, api_port):
            print(f"后端端口 {api_port} 已被占用。")
            print(f"换端口：python scripts/run_system.py --api-port {api_port + 1}")
            print("或自动找端口：python scripts/run_system.py --auto-port")
            raise SystemExit(1)

        if not is_port_available("127.0.0.1", web_port):
            print(f"前端端口 {web_port} 已被占用。")
            print(f"换端口：python scripts/run_system.py --web-port {web_port + 1}")
            print("或自动找端口：python scripts/run_system.py --auto-port")
            raise SystemExit(1)

    api_base_url = f"http://{host}:{api_port}"
    web_url = f"http://localhost:{web_port}"

    env = dict(os.environ)
    env["AGENT_API_BASE_URL"] = api_base_url
    env["FRONTEND_DEV_MODE"] = "1" if args.dev_mode else "0"

    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "api.server:app",
        "--host",
        host,
        "--port",
        str(api_port),
    ]
    if args.reload:
        api_cmd.append("--reload")

    web_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(PROJECT_ROOT / "app_api_streaming.py"),
        "--server.port",
        str(web_port),
        "--server.address",
        "127.0.0.1",
    ]

    api_proc: subprocess.Popen | None = None
    web_proc: subprocess.Popen | None = None

    try:
        api_proc = start_process("后端 API（含 /api/chat/stream）", api_cmd, env)

        print()
        print("等待后端 API 启动...")
        if not wait_for_api(host, api_port):
            print(f"后端 API 启动失败或超时：{api_base_url}")
            raise SystemExit(1)

        print(f"后端 API 已启动：{api_base_url}")
        print(f"API 文档：{api_base_url}/docs")
        print(f"流式接口：{api_base_url}/api/chat/stream")

        web_proc = start_process("前端页面（流式用户界面）", web_cmd, env)

        print()
        print("=" * 80)
        print("最终版系统已启动")
        print("=" * 80)
        print(f"后端 API：{api_base_url}")
        print(f"API 文档：{api_base_url}/docs")
        print(f"前端页面：{web_url}")
        print("按 Ctrl+C 停止系统。")

        if not args.no_browser:
            time.sleep(2)
            webbrowser.open(web_url)

        while True:
            time.sleep(1)
            if api_proc.poll() is not None:
                print("后端 API 已退出。")
                break
            if web_proc and web_proc.poll() is not None:
                print("前端页面已退出。")
                break

    except KeyboardInterrupt:
        print()
        print("收到 Ctrl+C，正在停止系统...")

    finally:
        for proc, name in [(web_proc, "前端"), (api_proc, "后端")]:
            if proc and proc.poll() is None:
                print(f"停止{name}进程 PID={proc.pid}")
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()

        print("系统已停止。")


if __name__ == "__main__":
    main()
