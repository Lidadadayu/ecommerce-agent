from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agent.human_review_queue import (  # noqa: E402
    get_human_review_task,
    list_human_review_tasks,
    update_human_review_task,
)


def _print_task_brief(task: dict) -> None:
    print(
        f"{task.get('review_id')} | "
        f"{task.get('status')} | "
        f"{task.get('created_at')} | "
        f"intent={task.get('intent')} | "
        f"risk={task.get('risk_level')}"
    )
    reasons = task.get("reasons") or []
    if reasons:
        print("  reasons:", "；".join(str(x) for x in reasons[:3]))
    print("  query:", task.get("user_query"))


def cmd_list(args: argparse.Namespace) -> None:
    tasks = list_human_review_tasks(status=args.status, limit=args.limit)
    if not tasks:
        print("暂无人工审核任务。")
        return

    for task in tasks:
        _print_task_brief(task)


def cmd_show(args: argparse.Namespace) -> None:
    task = get_human_review_task(args.review_id)
    if not task:
        print(f"未找到人工审核任务：{args.review_id}")
        return

    print(json.dumps(task, ensure_ascii=False, indent=2))


def cmd_update(args: argparse.Namespace) -> None:
    task = update_human_review_task(
        args.review_id,
        status=args.status,
        reviewer=args.reviewer,
        decision=args.decision,
        comment=args.comment,
    )

    if not task:
        print(f"未找到人工审核任务：{args.review_id}")
        return

    print("已更新：")
    print(json.dumps(task, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Human review queue console.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List review tasks.")
    list_parser.add_argument("--status", default=None, help="Filter by status, e.g. pending.")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.set_defaults(func=cmd_list)

    show_parser = subparsers.add_parser("show", help="Show one review task.")
    show_parser.add_argument("review_id")
    show_parser.set_defaults(func=cmd_show)

    update_parser = subparsers.add_parser("update", help="Update review task status.")
    update_parser.add_argument("review_id")
    update_parser.add_argument("--status", required=True, help="pending/approved/rejected/closed")
    update_parser.add_argument("--reviewer", default=None)
    update_parser.add_argument("--decision", default=None)
    update_parser.add_argument("--comment", default=None)
    update_parser.set_defaults(func=cmd_update)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
