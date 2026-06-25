from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from rag.knowledge_loader import KnowledgeDocument, load_knowledge_documents
from rag.query_expander import expand_query

try:
    from agent.domain_loader import get_domain_keywords
except Exception:
    def get_domain_keywords(group: str | None = None) -> list[str]:
        return []


IMPORTANT_TERMS = [
    "退货", "退款", "换货", "维修", "售后", "七天", "7天", "无理由", "质量问题", "人工审核",
    "包装", "拆封", "未拆封", "已拆封", "物流", "发货", "签收", "生鲜", "虚拟商品",
    "数码配件", "家用电器", "凭证", "工单", "取消订单", "催发货", "退款进度",
] + get_domain_keywords()



@dataclass
class BM25Result:
    doc: KnowledgeDocument
    score: float
    matched_terms: list[str]


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    tokens: list[str] = []

    for term in IMPORTANT_TERMS:
        if term.lower() in text:
            tokens.append(term.lower())

    for token in re.findall(r"[a-zA-Z0-9_]+", text):
        if len(token) >= 2:
            tokens.append(token)

    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    for i in range(len(chinese_chars) - 1):
        tokens.append("".join(chinese_chars[i : i + 2]))

    return tokens


def _domain_matches(doc: KnowledgeDocument, domain: str | None) -> bool:
    if not domain:
        return True

    metadata = doc.metadata or {}
    doc_domain = str(metadata.get("domain") or "").strip()

    if not doc_domain or doc_domain == "general":
        return True

    return doc_domain == domain


class BM25Retriever:
    def __init__(self, knowledge_dir: str | None = None, *, domain: str | None = None, k1: float = 1.5, b: float = 0.75) -> None:
        self.knowledge_dir = knowledge_dir
        self.domain = domain
        self.k1 = k1
        self.b = b
        self.documents = [doc for doc in load_knowledge_documents(knowledge_dir) if _domain_matches(doc, domain)]
        self.doc_tokens: list[list[str]] = []
        self.doc_freq: dict[str, int] = {}
        self.avg_doc_len = 0.0
        self._build_index()

    def _build_index(self) -> None:
        self.doc_tokens = []
        df_counter: defaultdict[str, int] = defaultdict(int)

        for doc in self.documents:
            text = f"{doc.title}\n{doc.category}\n{' '.join(doc.tags or [])}\n{doc.content}"
            tokens = tokenize(text)
            self.doc_tokens.append(tokens)

            for token in set(tokens):
                df_counter[token] += 1

        self.doc_freq = dict(df_counter)
        self.avg_doc_len = (
            sum(len(tokens) for tokens in self.doc_tokens) / len(self.doc_tokens)
            if self.doc_tokens else 0.0
        )

    def _idf(self, token: str) -> float:
        n_docs = len(self.documents)
        df = self.doc_freq.get(token, 0)
        if n_docs == 0:
            return 0.0
        return math.log(1 + (n_docs - df + 0.5) / (df + 0.5))

    def _score_doc(self, query_tokens: list[str], doc_index: int) -> tuple[float, list[str]]:
        tokens = self.doc_tokens[doc_index]
        if not tokens:
            return 0.0, []

        tf = Counter(tokens)
        doc_len = len(tokens)
        matched: list[str] = []
        score = 0.0

        for token in query_tokens:
            freq = tf.get(token, 0)
            if freq <= 0:
                continue

            matched.append(token)
            idf = self._idf(token)
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / max(self.avg_doc_len, 1))
            score += idf * numerator / denominator

        return score, matched

    def retrieve(self, query: str, *, top_k: int = 5, min_score: float = 0.05) -> list[BM25Result]:
        query_tokens: list[str] = []
        for expanded in expand_query(query):
            query_tokens.extend(tokenize(expanded))

        seen = set()
        query_tokens = [x for x in query_tokens if not (x in seen or seen.add(x))]

        results: list[BM25Result] = []
        for idx, doc in enumerate(self.documents):
            score, matched = self._score_doc(query_tokens, idx)
            if score >= min_score:
                results.append(BM25Result(doc=doc, score=score, matched_terms=matched))

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]
