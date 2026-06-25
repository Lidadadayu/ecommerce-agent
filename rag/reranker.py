from __future__ import annotations

from dataclasses import dataclass

from rag.knowledge_loader import KnowledgeDocument
from rag.query_expander import infer_category


@dataclass
class RerankInput:
    doc: KnowledgeDocument
    score: float
    matched_terms: list[str]
    source: str


@dataclass
class RerankOutput:
    doc: KnowledgeDocument
    score: float
    matched_terms: list[str]
    source: str


def rerank(query: str, items: list[RerankInput], *, top_k: int = 5) -> list[RerankOutput]:
    category = infer_category(query)
    query = query or ""

    outputs: list[RerankOutput] = []

    for item in items:
        score = item.score
        doc = item.doc

        if category and category == doc.category:
            score += 2.0

        if any(term in doc.title for term in ["总原则", "常见问题", "售后政策"]):
            score += 0.3

        if "人工审核" in query and ("人工审核" in doc.title or "人工审核" in doc.content):
            score += 1.5

        if "质量" in query and "质量问题" in doc.content:
            score += 1.2

        if "无理由" in query and "无理由" in doc.content:
            score += 1.2

        if "退款进度" in query and "退款进度" in doc.content:
            score += 1.2

        outputs.append(RerankOutput(doc=doc, score=score, matched_terms=item.matched_terms, source=item.source))

    outputs.sort(key=lambda x: x.score, reverse=True)
    return outputs[:top_k]
