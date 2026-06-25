from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    from api.server import app

    paths = sorted({getattr(route, "path", "") for route in app.routes})
    required = ["/api/health", "/api/chat", "/api/chat/stream", "/api/domain"]

    print("当前已注册 API 路由：")
    for path in paths:
        if path.startswith("/api"):
            print("-", path)

    missing = [path for path in required if path not in paths]
    if missing:
        print()
        print("缺失关键路由：")
        for path in missing:
            print("-", path)
        raise SystemExit(1)

    print()
    print("入口检查通过：普通聊天和流式聊天接口均已注册。")


if __name__ == "__main__":
    main()
