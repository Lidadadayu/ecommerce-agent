from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="向量库 similarity search 演示。")
    parser.add_argument("query", help="查询问题")
    parser.add_argument("--domain", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--category", default=None)
    args = parser.parse_args()

    from agent.domain_loader import load_domain_config
    from rag.vector_store import similarity_search

    domain = load_domain_config(args.domain)
    try:
        results = similarity_search(args.query, domain_id=domain.domain_id, top_k=args.top_k, category=args.category)
    except Exception as exc:
        print(f"向量检索失败：{type(exc).__name__}: {exc}")
        print("请先确认已运行：python scripts\\build_vector_store.py --domain robot_vacuum --reset")
        raise SystemExit(1) from exc

    if not results:
        print("没有检索到结果。")
        print("请先确认已运行：python scripts\\build_vector_store.py --domain robot_vacuum --reset")
        raise SystemExit(0)

    for idx, item in enumerate(results, start=1):
        print(f"\n[{idx}] score={item.score} distance={item.distance}")
        print(f"title: {item.doc.title}")
        print(f"source: {item.doc.source}")
        print(item.doc.content[:500])


if __name__ == "__main__":
    main()
