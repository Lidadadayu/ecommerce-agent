from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agent.run_logger import load_run_logs, summarize_logs  # noqa: E402


def cmd_list(args: argparse.Namespace) -> None:
    records = load_run_logs(date_text=args.date, limit=args.limit)

    if not records:
        print("暂无 Agent 运行日志。")
        return

    for item in records:
        print(
            f"{item.get('created_at')} | "
            f"{item.get('run_id')} | "
            f"intent={item.get('intent')} | "
            f"tool={item.get('tool_name')} | "
            f"mode={item.get('mode')} | "
            f"{item.get('elapsed_ms')}ms"
        )
        print(f"  Q: {item.get('user_query')}")
        answer = str(item.get("final_answer_preview") or "").replace("\n", " ")
        if len(answer) > 180:
            answer = answer[:180] + "..."
        print(f"  A: {answer}")


def cmd_show(args: argparse.Namespace) -> None:
    records = load_run_logs(date_text=args.date, limit=10000)

    for item in records:
        if item.get("run_id") == args.run_id:
            print(json.dumps(item, ensure_ascii=False, indent=2))
            return

    print(f"未找到运行日志：{args.run_id}")


def cmd_stats(args: argparse.Namespace) -> None:
    records = load_run_logs(date_text=args.date, limit=args.limit)
    summary = summarize_logs(records)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="查看 Agent 运行日志。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="列出最近运行日志")
    list_parser.add_argument("--date", default=None, help="日期，例如 20260623。默认今天。")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.set_defaults(func=cmd_list)

    show_parser = subparsers.add_parser("show", help="查看单条运行日志详情")
    show_parser.add_argument("run_id")
    show_parser.add_argument("--date", default=None, help="日期，例如 20260623。默认今天。")
    show_parser.set_defaults(func=cmd_show)

    stats_parser = subparsers.add_parser("stats", help="统计最近运行日志")
    stats_parser.add_argument("--date", default=None, help="日期，例如 20260623。默认今天。")
    stats_parser.add_argument("--limit", type=int, default=200)
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
