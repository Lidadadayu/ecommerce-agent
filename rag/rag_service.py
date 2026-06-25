from __future__ import annotations

from typing import Any

from agent.domain_loader import get_active_domain_id
from rag.hybrid_retriever import HybridRetrievedChunk, retrieve_hybrid_documents


def _format_chunk(index: int, chunk: HybridRetrievedChunk) -> str:
    doc = chunk.doc
    content = doc.content.strip()
    if len(content) > 700:
        content = content[:700] + "..."

    tags = "、".join(doc.tags or [])
    tag_text = f"；标签：{tags}" if tags else ""

    return (
        f"[{index}] {doc.title}\n"
        f"类别：{doc.category}{tag_text}\n"
        f"检索来源：{chunk.source}；相关度：{round(chunk.score, 4)}\n"
        f"内容：{content}"
    )


def build_rag_context(
    query: str,
    *,
    category: str | None = None,
    top_k: int = 4,
    knowledge_dir: str | None = None,
    domain: str | None = None,
) -> str:
    chunks = retrieve_hybrid_documents(
        query,
        category=category,
        top_k=top_k,
        knowledge_dir=knowledge_dir,
        domain=domain or get_active_domain_id(),
    )

    if not chunks:
        return ""

    lines = ["【知识库检索结果】"]
    for idx, chunk in enumerate(chunks, start=1):
        lines.append(_format_chunk(idx, chunk))

    return "\n\n".join(lines)


def retrieve_knowledge(
    query: str,
    *,
    category: str | None = None,
    top_k: int = 4,
    knowledge_dir: str | None = None,
    domain: str | None = None,
) -> list[dict[str, Any]]:
    chunks = retrieve_hybrid_documents(
        query,
        category=category,
        top_k=top_k,
        knowledge_dir=knowledge_dir,
        domain=domain or get_active_domain_id(),
    )

    return [
        {
            "doc_id": chunk.doc.doc_id,
            "title": chunk.doc.title,
            "content": chunk.doc.content,
            "source": chunk.doc.source,
            "category": chunk.doc.category,
            "tags": chunk.doc.tags or [],
            "score": round(chunk.score, 4),
            "matched_terms": chunk.matched_terms,
            "retrieval_source": chunk.source,
            "metadata": chunk.doc.metadata or {},
        }
        for chunk in chunks
    ]


def answer_policy_question(
    user_query: str,
    *,
    category: str | None = None,
    base_answer: str | None = None,
    top_k: int = 4,
) -> str:
    rag_context = build_rag_context(user_query, category=category, top_k=top_k)

    if not rag_context:
        if base_answer:
            return base_answer
        return "知识库中暂未检索到足够相关的政策内容。建议补充商品类别或转人工客服确认。"

    try:
        from agent.llm_client import chat_with_llm
    except Exception:
        if base_answer:
            return f"{base_answer}\n\n知识库补充：\n{rag_context}"
        return rag_context

    prompt = f"""
你是电商售后与运营 Agent 的政策解释助手。

用户问题：
{user_query}

已有业务工具结果：
{base_answer or "无"}

{rag_context}

请基于“已有业务工具结果”和“知识库检索结果”回答用户。

严格要求：
1. 不要编造知识库中没有的政策。
2. 不要承诺“必定退款成功”“必定退货成功”“一定赔付”。
3. 如果涉及具体订单能否退货，必须说明最终以订单状态、商品类别、售后规则和人工审核为准。
4. 如果已有业务工具结果给出了明确结论，不能推翻它，只能补充解释。
5. 语气像电商客服，简洁清楚。
"""

    result = chat_with_llm(
        user_query=prompt,
        temperature=0.2,
        max_tokens=700,
        fallback_content=(base_answer or "") + "\n\n知识库补充：\n" + rag_context,
    )

    return result.get("content") or base_answer or rag_context
