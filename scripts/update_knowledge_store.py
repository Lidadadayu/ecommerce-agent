from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="构建/增量更新知识分片存储。")
    parser.add_argument("--domain", default=None, help="领域 ID，默认读取 ACTIVE_DOMAIN。")
    parser.add_argument("--max-chars", type=int, default=900)
    args = parser.parse_args()

    from agent.domain_loader import get_active_domain_config
    from rag.knowledge_chunk_store import build_knowledge_chunk_store

    domain = get_active_domain_config(args.domain) if args.domain else get_active_domain_config()
    output_dir = PROJECT_ROOT / "data" / "runtime" / "knowledge_store" / domain.domain_id

    manifest = build_knowledge_chunk_store(
        knowledge_dir=domain.knowledge_dir,
        output_dir=output_dir,
        domain_id=domain.domain_id,
        max_chars=args.max_chars,
    )

    print("知识分片存储已更新：")
    print(f"- domain_id: {manifest['domain_id']}")
    print(f"- chunks_file: {manifest['chunks_file']}")
    print(f"- reused_files: {manifest['stats']['reused_files']}")
    print(f"- updated_files: {manifest['stats']['updated_files']}")
    print(f"- chunks: {manifest['stats']['chunks']}")


if __name__ == "__main__":
    main()
