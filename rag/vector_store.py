from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag.embedding_client import EmbeddingProvider, get_embedding_client
from rag.knowledge_chunk_store import KnowledgeChunk, build_knowledge_chunk_store, load_chunks
from rag.knowledge_loader import KnowledgeDocument


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "data" / "runtime"


@dataclass
class VectorSearchResult:
    doc: KnowledgeDocument
    score: float
    distance: float | None
    matched_terms: list[str]


def _safe_collection_name(domain_id: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_-]+", "_", domain_id.strip() or "default")
    name = f"kb_{name}"
    return name[:63]


def _require_chromadb():
    try:
        import chromadb
    except Exception as exc:
        raise RuntimeError("chromadb is not installed. Please install chromadb in py312 environment.") from exc
    return chromadb


def _chunk_to_document(chunk: KnowledgeChunk, metadata: dict[str, Any] | None = None) -> KnowledgeDocument:
    return KnowledgeDocument(
        doc_id=chunk.chunk_id,
        title=chunk.title,
        content=chunk.content,
        source=chunk.source_file,
        category=chunk.category or "general",
        tags=[],
        metadata=metadata or {
            "domain": chunk.domain_id,
            "doc_id": chunk.doc_id,
            "source_file": chunk.source_file,
            "chunk_id": chunk.chunk_id,
        },
    )


def _metadata_for_chunk(chunk: KnowledgeChunk) -> dict[str, Any]:
    return {
        "domain_id": chunk.domain_id,
        "doc_id": chunk.doc_id,
        "source_file": chunk.source_file,
        "source_hash": chunk.source_hash,
        "title": chunk.title,
        "category": chunk.category or "general",
        "version": chunk.version,
        "enabled": bool(chunk.enabled),
        "updated_at": chunk.updated_at,
    }


class ChromaVectorKnowledgeStore:
    def __init__(
        self,
        *,
        domain_id: str,
        persist_dir: Path | str | None = None,
        embedding_client: EmbeddingProvider | None = None,
    ) -> None:
        self.domain_id = domain_id
        self.persist_dir = Path(persist_dir) if persist_dir else DEFAULT_RUNTIME_DIR / "vector_store" / domain_id
        self.embedding_client = embedding_client or get_embedding_client()
        self.collection_name = _safe_collection_name(domain_id)

    def _collection(self):
        chromadb = _require_chromadb()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.persist_dir))
        return client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine", "domain_id": self.domain_id},
        )

    def upsert_chunks(self, chunks: list[KnowledgeChunk], *, batch_size: int = 64, reset: bool = False) -> dict[str, Any]:
        enabled = [chunk for chunk in chunks if chunk.enabled and chunk.content.strip()]
        chromadb = _require_chromadb()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.persist_dir))
        if reset:
            try:
                client.delete_collection(self.collection_name)
            except Exception:
                pass
        collection = client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine", "domain_id": self.domain_id},
        )

        total = 0
        for start in range(0, len(enabled), batch_size):
            batch = enabled[start:start + batch_size]
            texts = [f"{chunk.title}\n{chunk.content}" for chunk in batch]
            embeddings = self.embedding_client.embed_documents(texts)
            collection.upsert(
                ids=[chunk.chunk_id for chunk in batch],
                documents=[chunk.content for chunk in batch],
                metadatas=[_metadata_for_chunk(chunk) for chunk in batch],
                embeddings=embeddings,
            )
            total += len(batch)

        return {
            "success": True,
            "domain_id": self.domain_id,
            "collection_name": self.collection_name,
            "persist_dir": str(self.persist_dir),
            "upserted": total,
            "total_chunks": len(enabled),
        }

    def similarity_search(self, query: str, *, top_k: int = 5, category: str | None = None) -> list[VectorSearchResult]:
        query = (query or "").strip()
        if not query:
            return []
        collection = self._collection()
        query_embedding = self.embedding_client.embed_query(query)
        where = {"category": category} if category else None
        raw = collection.query(
            query_embeddings=[query_embedding],
            n_results=max(1, int(top_k)),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        results: list[VectorSearchResult] = []
        for idx, chunk_id in enumerate(ids):
            metadata = metadatas[idx] or {}
            distance = distances[idx] if idx < len(distances) else None
            score = 1.0 - float(distance) if distance is not None else 0.0
            doc = KnowledgeDocument(
                doc_id=str(chunk_id),
                title=str(metadata.get("title") or chunk_id),
                content=str(documents[idx] if idx < len(documents) else ""),
                source=str(metadata.get("source_file") or ""),
                category=str(metadata.get("category") or "general"),
                tags=[],
                metadata=dict(metadata),
            )
            results.append(VectorSearchResult(doc=doc, score=round(score, 6), distance=distance, matched_terms=[]))
        return results


def build_vector_store_from_chunks(
    *,
    domain_id: str,
    chunks_file: Path,
    persist_dir: Path | None = None,
    embedding_client: EmbeddingProvider | None = None,
    reset: bool = False,
) -> dict[str, Any]:
    chunks = load_chunks(chunks_file)
    store = ChromaVectorKnowledgeStore(domain_id=domain_id, persist_dir=persist_dir, embedding_client=embedding_client)
    result = store.upsert_chunks(chunks, reset=reset)
    result["chunks_file"] = str(chunks_file)
    manifest_file = Path(result["persist_dir"]) / "manifest.json"
    manifest_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def build_chunk_and_vector_store(
    *,
    domain_id: str,
    knowledge_dir: Path,
    output_dir: Path,
    max_chars: int = 900,
    reset: bool = False,
    embedding_client: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    chunk_manifest = build_knowledge_chunk_store(
        knowledge_dir=knowledge_dir,
        output_dir=output_dir,
        domain_id=domain_id,
        max_chars=max_chars,
    )
    vector_manifest = build_vector_store_from_chunks(
        domain_id=domain_id,
        chunks_file=Path(chunk_manifest["chunks_file"]),
        persist_dir=DEFAULT_RUNTIME_DIR / "vector_store" / domain_id,
        embedding_client=embedding_client,
        reset=reset,
    )
    return {"chunks": chunk_manifest, "vectors": vector_manifest}


def similarity_search(
    query: str,
    *,
    domain_id: str,
    top_k: int = 5,
    category: str | None = None,
    persist_dir: Path | None = None,
    embedding_client: EmbeddingProvider | None = None,
) -> list[VectorSearchResult]:
    store = ChromaVectorKnowledgeStore(domain_id=domain_id, persist_dir=persist_dir, embedding_client=embedding_client)
    return store.similarity_search(query, top_k=top_k, category=category)
