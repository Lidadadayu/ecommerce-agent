from __future__ import annotations

import argparse
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "venv",
    ".venv",
    "env",
    "chroma_db",
    "node_modules",
}

DEFAULT_EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
}

DEFAULT_EXCLUDE_FILES = {
    ".env",
}


def should_skip(path: Path) -> bool:
    rel_parts = set(path.relative_to(PROJECT_ROOT).parts)

    if rel_parts & DEFAULT_EXCLUDE_DIRS:
        return True

    if path.name in DEFAULT_EXCLUDE_FILES:
        return True

    if path.suffix in DEFAULT_EXCLUDE_SUFFIXES:
        return True

    # 运行日志可再生成，打包时默认排除，避免包含过多对话内容。
    rel_text = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    if rel_text.startswith("data/runtime/"):
        return True

    return False


def export_snapshot(output: Path) -> Path:
    if output.exists():
        output.unlink()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in PROJECT_ROOT.rglob("*"):
            if path.is_dir():
                continue
            if should_skip(path):
                continue
            zf.write(path, path.relative_to(PROJECT_ROOT))

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="导出可复现项目快照。")
    parser.add_argument("--output", default=None, help="输出 zip 路径。")
    args = parser.parse_args()

    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = PROJECT_ROOT / output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = PROJECT_ROOT / "dist" / f"ecommerce_agent_snapshot_{timestamp}.zip"

    output.parent.mkdir(parents=True, exist_ok=True)
    export_snapshot(output)

    print(f"已导出项目快照：{output}")
    print("注意：.env、运行日志、缓存、虚拟环境不会被打包。")


if __name__ == "__main__":
    main()
