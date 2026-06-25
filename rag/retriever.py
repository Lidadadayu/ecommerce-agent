from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from rag.knowledge_loader import KnowledgeDocument, load_knowledge_documents


try:
    from agent.domain_loader import get_domain_keywords
except Exception:
    def get_domain_keywords(group: str | None = None) -> list[str]:
        return []


IMPORTANT_TERMS = [
    "退货",
    "退款",
    "换货",
    "维修",
    "售后",
    "七天",
    "7天",
    "无理由",
    "质量问题",
    "人工审核",
    "包装",
    "拆封",
    "未拆封",
    "已拆封",
    "物流",
    "发货",
    "签收",
    "生鲜",
    "虚拟商品",
    "数码配件",
    "家用电器",
    "凭证",
    "工单",
    "取消订单",
] + get_domain_keywords()



@dataclass
class RetrievedChunk:
    doc: KnowledgeDocument
    score: float
    matched_terms: list[str]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _extract_terms(text: str) -> list[str]:
    text = _normalize(text)
    terms: set[str] = set()

    # 英文/数字词
    for token in re.findall(r"[a-zA-Z0-9_]+", text):
        if len(token) >= 2:
            terms.add(token)

    # 重要中文业务词
    for term in IMPORTANT_TERMS:
        if term.lower() in text:
            terms.add(term.lower())

    # 中文 bigram，解决“用户表达”和“知识库表达”不完全一致时的召回问题
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    for i in range(len(chinese_chars) - 1):
        terms.add("".join(chinese_chars[i : i + 2]))

    return list(terms)


def _score_document(query_terms: list[str], doc: KnowledgeDocument, category: str | None = None) -> tuple[float, list[str]]:
    title = _normalize(doc.title)
    content = _normalize(doc.content)
    doc_category = _normalize(doc.category or "")
    tags = " ".join(doc.tags or [])
    tags = _normalize(tags)

    matched: list[str] = []
    score = 0.0

    if category and category in (doc.category or ""):
        score += 3.0

    for term in query_terms:
        term_score = 0.0

        if term in title:
            term_score += 3.0

        if term in doc_category:
            term_score += 2.2

        if term in tags:
            term_score += 2.0

        count = content.count(term)
        if count:
            term_score += 1.0 + math.log(1 + count)

        if term_score > 0:
            matched.append(term)
            score += term_score

    # 稍微偏向短而聚焦的 chunk，避免过长文档靠词频刷高分。
    length_penalty = max(len(doc.content) / 1000, 1.0)
    score = score / length_penalty

    return score, matched


def _domain_matches(doc: KnowledgeDocument, domain: str | None) -> bool:
    if not domain:
        return True

    metadata = doc.metadata or {}
    doc_domain = str(metadata.get("domain") or "").strip()

    # 通用政策类文档保留；其他领域专属文档按 ACTIVE_DOMAIN 过滤。
    if not doc_domain or doc_domain == "general":
        return True

    return doc_domain == domain


class SimpleKnowledgeRetriever:
    """
    简化版检索器。

    设计原因：
    - 第一版先不引入 Chroma、BM25、reranker，降低工程复杂度。
    - 对售后政策/FAQ 这种短文本知识库，关键词 + 中文 bigram 已经能覆盖很多场景。
    - 后续可以在这个接口下替换为 Chroma 或混合检索，不影响 Agent 主流程。
    """

    def __init__(self, knowledge_dir: str | None = None, domain: str | None = None) -> None:
        self.knowledge_dir = knowledge_dir
        self.domain = domain
        self.documents = [doc for doc in load_knowledge_documents(knowledge_dir) if _domain_matches(doc, domain)]

    def reload(self) -> None:
        self.documents = [doc for doc in load_knowledge_documents(self.knowledge_dir) if _domain_matches(doc, self.domain)]

    def retrieve(
        self,
        query: str,
        *,
        category: str | None = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[RetrievedChunk]:
        query_terms = _extract_terms(query)
        if category:
            query_terms.extend(_extract_terms(category))

        results: list[RetrievedChunk] = []

        for doc in self.documents:
            score, matched = _score_document(query_terms, doc, category=category)
            if score >= min_score:
                results.append(RetrievedChunk(doc=doc, score=score, matched_terms=matched))

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]


def retrieve_documents(
    query: str,
    *,
    category: str | None = None,
    top_k: int = 5,
    knowledge_dir: str | None = None,
    domain: str | None = None,
) -> list[RetrievedChunk]:
    retriever = SimpleKnowledgeRetriever(knowledge_dir=knowledge_dir, domain=domain)
    return retriever.retrieve(query, category=category, top_k=top_k)
