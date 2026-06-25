from __future__ import annotations

import argparse
import socket


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) != 0


def main() -> None:
    parser = argparse.ArgumentParser(description="检查端口是否被占用。")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--ports", nargs="+", type=int, default=[8000, 8001, 8501, 8502])
    args = parser.parse_args()

    for port in args.ports:
        status = "可用" if is_port_available(args.host, port) else "已占用"
        print(f"{args.host}:{port} -> {status}")


if __name__ == "__main__":
    main()
