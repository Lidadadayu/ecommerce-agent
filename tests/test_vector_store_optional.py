from __future__ import annotations

import pytest


def test_vector_store_import_is_lightweight() -> None:
    import rag.vector_store as vector_store

    assert hasattr(vector_store, "ChromaVectorKnowledgeStore")


def test_chroma_vector_store_roundtrip_when_chromadb_available(tmp_path) -> None:
    pytest.importorskip("chromadb")

    from rag.knowledge_chunk_store import KnowledgeChunk
    from rag.vector_store import ChromaVectorKnowledgeStore

    class FakeEmbeddingClient:
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] if "不出水" in text else [0.0, 1.0] for text in texts]

        def embed_query(self, text: str) -> list[float]:
            return [1.0, 0.0]

    store = ChromaVectorKnowledgeStore(
        domain_id="test_domain",
        persist_dir=tmp_path,
        embedding_client=FakeEmbeddingClient(),
    )
    store.upsert_chunks(
        [
            KnowledgeChunk(
                chunk_id="c1",
                domain_id="test_domain",
                doc_id="d1",
                source_file="a.md",
                source_hash="h1",
                title="拖地不出水",
                content="水箱未安装到位、出水孔堵塞都会导致拖地不出水。",
                category="robot_vacuum_troubleshooting",
            ),
            KnowledgeChunk(
                chunk_id="c2",
                domain_id="test_domain",
                doc_id="d2",
                source_file="b.md",
                source_hash="h2",
                title="选购建议",
                content="预算和户型会影响扫地机器人选购。",
                category="robot_vacuum_buying_guide",
            ),
        ],
        reset=True,
    )

    results = store.similarity_search("拖地时不出水怎么办", top_k=1)

    assert results
    assert results[0].doc.doc_id == "c1"
