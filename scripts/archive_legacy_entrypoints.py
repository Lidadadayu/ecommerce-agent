from __future__ import annotations

import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = PROJECT_ROOT / "archive" / "legacy_entrypoints"


LEGACY_FILES = [
    "README_REFACTOR.md",
    "RUN_SYSTEM.md",
    "docs/RUN_SYSTEM.md",
]


def main() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    moved: list[str] = []
    skipped: list[str] = []

    for rel in LEGACY_FILES:
        src = PROJECT_ROOT / rel
        if not src.exists():
            skipped.append(rel)
            continue

        dst = ARCHIVE_DIR / rel.replace("/", "__")
        if dst.exists():
            skipped.append(rel)
            continue

        shutil.move(str(src), str(dst))
        moved.append(rel)

    print("已归档：")
    for item in moved:
        print("-", item)

    print()
    print("跳过：")
    for item in skipped:
        print("-", item)

    print()
    print("说明：本脚本只归档旧文档，不移动 app.py/app_api.py 等兼容入口，避免旧命令失效。")


if __name__ == "__main__":
    main()
