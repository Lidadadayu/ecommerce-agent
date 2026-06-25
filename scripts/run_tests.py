from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    try:
        import pytest  # noqa: F401
    except Exception:
        print("未检测到 pytest，请先安装：")
        print("pip install -r requirements-dev.txt")
        raise SystemExit(1)

    cmd = [sys.executable, "-m", "pytest", "-q", "tests"]
    print("运行命令：", " ".join(cmd))
    raise SystemExit(subprocess.call(cmd, cwd=str(PROJECT_ROOT)))


if __name__ == "__main__":
    main()
