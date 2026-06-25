from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="构建知识分片并写入 Chroma 向量库。")
    parser.add_argument("--domain", default=None, help="领域 ID，默认读取 ACTIVE_DOMAIN。")
    parser.add_argument("--max-chars", type=int, default=900, help="文档切分最大字符数。")
    parser.add_argument("--reset", action="store_true", help="重建 Chroma collection。")
    args = parser.parse_args()

    from agent.domain_loader import load_domain_config
    from rag.embedding_client import embedding_config
    from rag.vector_store import build_chunk_and_vector_store

    domain = load_domain_config(args.domain)
    output_dir = PROJECT_ROOT / "data" / "runtime" / "knowledge_store" / domain.domain_id

    print("Embedding 配置：")
    config = embedding_config()
    print(f"- model: {config['model']}")
    print(f"- base_url: {config['base_url']}")
    print(f"- has_api_key: {config['has_api_key']}")

    manifest = build_chunk_and_vector_store(
        domain_id=domain.domain_id,
        knowledge_dir=domain.knowledge_dir,
        output_dir=output_dir,
        max_chars=args.max_chars,
        reset=args.reset,
    )

    print("向量知识库已更新：")
    print(f"- domain_id: {domain.domain_id}")
    print(f"- chunks_file: {manifest['chunks']['chunks_file']}")
    print(f"- chunks: {manifest['chunks']['stats']['chunks']}")
    print(f"- vector_dir: {manifest['vectors']['persist_dir']}")
    print(f"- collection: {manifest['vectors']['collection_name']}")
    print(f"- upserted: {manifest['vectors']['upserted']}")


if __name__ == "__main__":
    main()
