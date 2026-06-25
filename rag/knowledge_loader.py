from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge"


@dataclass
class KnowledgeDocument:
    doc_id: str
    title: str
    content: str
    source: str
    category: str = "general"
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """
    支持简单 front matter：

    ---
    title: 数码配件售后政策
    category: 数码配件
    tags: 退货, 换货, 质量问题
    ---
    正文
    """

    text = _clean_text(text)
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    raw_meta = parts[1].strip()
    body = parts[2].strip()

    metadata: dict[str, str] = {}
    for line in raw_meta.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()

    return metadata, body


def _split_markdown_sections(text: str, source: str, default_title: str) -> list[KnowledgeDocument]:
    metadata, body = _parse_front_matter(text)

    title = metadata.get("title") or default_title
    category = metadata.get("category") or "general"
    tags = [t.strip() for t in (metadata.get("tags") or "").split(",") if t.strip()]

    chunks: list[KnowledgeDocument] = []

    # 按二级标题切分；没有二级标题则按段落聚合。
    section_pattern = re.compile(r"(?m)^##\s+(.+?)\s*$")
    matches = list(section_pattern.finditer(body))

    if matches:
        for idx, match in enumerate(matches):
            section_title = match.group(1).strip()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
            content = _clean_text(body[start:end])
            if not content:
                continue

            chunks.append(
                KnowledgeDocument(
                    doc_id=f"{Path(source).stem}-{idx + 1}",
                    title=f"{title} - {section_title}",
                    content=content,
                    source=source,
                    category=category,
                    tags=tags,
                    metadata=metadata,
                )
            )
    else:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        current: list[str] = []
        current_len = 0
        chunk_id = 1

        for paragraph in paragraphs:
            if current_len + len(paragraph) > 900 and current:
                chunks.append(
                    KnowledgeDocument(
                        doc_id=f"{Path(source).stem}-{chunk_id}",
                        title=title,
                        content=_clean_text("\n\n".join(current)),
                        source=source,
                        category=category,
                        tags=tags,
                        metadata=metadata,
                    )
                )
                chunk_id += 1
                current = []
                current_len = 0

            current.append(paragraph)
            current_len += len(paragraph)

        if current:
            chunks.append(
                KnowledgeDocument(
                    doc_id=f"{Path(source).stem}-{chunk_id}",
                    title=title,
                    content=_clean_text("\n\n".join(current)),
                    source=source,
                    category=category,
                    tags=tags,
                    metadata=metadata,
                )
            )

    return chunks


def _load_json_file(path: Path) -> list[KnowledgeDocument]:
    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, dict):
        data = data.get("documents") or data.get("items") or []

    if not isinstance(data, list):
        return []

    docs: list[KnowledgeDocument] = []

    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or f"{path.stem}-{idx}")
        content = str(item.get("content") or item.get("text") or "").strip()
        if not content:
            continue

        tags = item.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        docs.append(
            KnowledgeDocument(
                doc_id=str(item.get("doc_id") or f"{path.stem}-{idx}"),
                title=title,
                content=content,
                source=str(path),
                category=str(item.get("category") or "general"),
                tags=tags,
                metadata=item.get("metadata") or {},
            )
        )

    return docs


def load_knowledge_documents(knowledge_dir: str | Path | None = None) -> list[KnowledgeDocument]:
    """
    加载 data/knowledge 下的知识文档。

    支持：
    - .md
    - .txt
    - .json

    第一版 RAG 不依赖 Chroma / BM25 / reranker，先保证稳定可用。
    """

    root = Path(knowledge_dir) if knowledge_dir else DEFAULT_KNOWLEDGE_DIR
    if not root.exists():
        return []

    docs: list[KnowledgeDocument] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()

        if suffix in {".md", ".txt"}:
            text = path.read_text(encoding="utf-8")
            docs.extend(_split_markdown_sections(text, str(path), path.stem))

        elif suffix == ".json":
            docs.extend(_load_json_file(path))

    return docs
