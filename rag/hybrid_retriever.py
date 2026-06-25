from __future__ import annotations

from dataclasses import dataclass

from rag.bm25_retriever import BM25Retriever
from rag.knowledge_loader import KnowledgeDocument
from rag.reranker import RerankInput, rerank
from rag.retriever import SimpleKnowledgeRetriever
from rag.vector_store import similarity_search


@dataclass
class HybridRetrievedChunk:
    doc: KnowledgeDocument
    score: float
    matched_terms: list[str]
    source: str


class HybridKnowledgeRetriever:
    def __init__(self, knowledge_dir: str | None = None, domain: str | None = None) -> None:
        self.knowledge_dir = knowledge_dir
        self.domain = domain
        self.simple = SimpleKnowledgeRetriever(knowledge_dir=knowledge_dir, domain=domain)
        self.bm25 = BM25Retriever(knowledge_dir=knowledge_dir, domain=domain)

    def retrieve(self, query: str, *, category: str | None = None, top_k: int = 5) -> list[HybridRetrievedChunk]:
        simple_results = self.simple.retrieve(
            query,
            category=category,
            top_k=max(top_k * 2, 6),
            min_score=0.2,
        )
        bm25_results = self.bm25.retrieve(
            query,
            top_k=max(top_k * 2, 6),
            min_score=0.05,
        )
        vector_results = []
        if self.domain:
            try:
                vector_results = similarity_search(
                    query,
                    domain_id=self.domain,
                    category=category,
                    top_k=max(top_k * 2, 6),
                )
            except Exception:
                # 向量库未构建、无 embedding key 或 chromadb 不可用时，保留 BM25/关键词召回。
                vector_results = []

        merged: dict[str, RerankInput] = {}

        for item in simple_results:
            merged[item.doc.doc_id] = RerankInput(
                doc=item.doc,
                score=item.score * 0.55,
                matched_terms=item.matched_terms,
                source="simple",
            )

        for item in bm25_results:
            doc_id = item.doc.doc_id
            score = item.score * 0.45

            if doc_id in merged:
                old = merged[doc_id]
                merged[doc_id] = RerankInput(
                    doc=old.doc,
                    score=old.score + score,
                    matched_terms=list(dict.fromkeys(old.matched_terms + item.matched_terms)),
                    source="hybrid",
                )
            else:
                merged[doc_id] = RerankInput(
                    doc=item.doc,
                    score=score,
                    matched_terms=item.matched_terms,
                    source="bm25",
                )

        for item in vector_results:
            doc_id = item.doc.doc_id
            score = max(float(item.score), 0.0) * 0.75

            if doc_id in merged:
                old = merged[doc_id]
                merged[doc_id] = RerankInput(
                    doc=old.doc,
                    score=old.score + score,
                    matched_terms=old.matched_terms,
                    source="hybrid_vector",
                )
            else:
                merged[doc_id] = RerankInput(
                    doc=item.doc,
                    score=score,
                    matched_terms=item.matched_terms,
                    source="vector",
                )

        return [
            HybridRetrievedChunk(
                doc=item.doc,
                score=item.score,
                matched_terms=item.matched_terms,
                source=item.source,
            )
            for item in rerank(query, list(merged.values()), top_k=top_k)
        ]


def retrieve_hybrid_documents(
    query: str,
    *,
    category: str | None = None,
    top_k: int = 5,
    knowledge_dir: str | None = None,
    domain: str | None = None,
) -> list[HybridRetrievedChunk]:
    return HybridKnowledgeRetriever(knowledge_dir=knowledge_dir, domain=domain).retrieve(query, category=category, top_k=top_k)
