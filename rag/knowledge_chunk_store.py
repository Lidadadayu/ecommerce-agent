from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_text(path.read_text(encoding="utf-8", errors="ignore"))


@dataclass
class KnowledgeChunk:
    chunk_id: str
    domain_id: str
    doc_id: str
    source_file: str
    source_hash: str
    title: str
    content: str
    category: str | None = None
    version: str = "v1"
    enabled: bool = True
    updated_at: str = ""


def infer_category(path: Path) -> str:
    name = path.stem.lower()
    mapping = {
        "troubleshooting": "robot_vacuum_troubleshooting",
        "maintenance": "robot_vacuum_maintenance",
        "buying": "robot_vacuum_buying_guide",
        "faq": "robot_vacuum_faq",
        "policy": "robot_vacuum_aftersale_policy",
        "aftersale": "robot_vacuum_aftersale_policy",
    }
    for key, category in mapping.items():
        if key in name:
            return category
    if "故障" in path.stem:
        return "robot_vacuum_troubleshooting"
    if "维修" in path.stem or "保养" in path.stem:
        return "robot_vacuum_maintenance"
    if "选购" in path.stem:
        return "robot_vacuum_buying_guide"
    return "general"


def split_markdown(content: str, *, max_chars: int = 900) -> list[tuple[str, str]]:
    """
    轻量 Markdown 分片：
    1. 优先按标题切；
    2. 大段再按字符长度切；
    3. 每个 chunk 保留 title。
    """

    lines = content.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_title = "未命名片段"
    current_lines: list[str] = []

    heading_pattern = re.compile(r"^\s{0,3}#{1,6}\s+(.+)$")

    for line in lines:
        match = heading_pattern.match(line)
        if match:
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = match.group(1).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_title, current_lines))

    chunks: list[tuple[str, str]] = []
    for title, section_lines in sections:
        text = "\n".join(section_lines).strip()
        if not text:
            continue

        if len(text) <= max_chars:
            chunks.append((title, text))
            continue

        paragraphs = re.split(r"\n\s*\n", text)
        buf = ""
        part_idx = 1
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(buf) + len(para) + 2 <= max_chars:
                buf = (buf + "\n\n" + para).strip()
            else:
                if buf:
                    chunks.append((f"{title} - {part_idx}", buf))
                    part_idx += 1
                if len(para) <= max_chars:
                    buf = para
                else:
                    for i in range(0, len(para), max_chars):
                        chunks.append((f"{title} - {part_idx}", para[i:i + max_chars]))
                        part_idx += 1
                    buf = ""
        if buf:
            chunks.append((f"{title} - {part_idx}", buf))

    return chunks


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def save_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def build_knowledge_chunk_store(
    *,
    knowledge_dir: Path,
    output_dir: Path,
    domain_id: str,
    max_chars: int = 900,
) -> dict[str, Any]:
    """
    构建或增量更新知识分片存储。

    输出：
    - chunks.jsonl
    - manifest.json

    如果文件 hash 未变化，复用旧 chunks。
    如果文件 hash 变化，只重建该文件对应 chunks。
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    chunks_file = output_dir / "chunks.jsonl"
    manifest_file = output_dir / "manifest.json"

    old_chunks = load_jsonl(chunks_file)
    old_by_file: dict[str, list[dict[str, Any]]] = {}
    for row in old_chunks:
        old_by_file.setdefault(row.get("source_file", ""), []).append(row)

    old_manifest: dict[str, Any] = {}
    if manifest_file.exists():
        try:
            old_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            old_manifest = {}

    old_hashes = old_manifest.get("file_hashes", {}) if isinstance(old_manifest.get("file_hashes"), dict) else {}

    new_rows: list[dict[str, Any]] = []
    new_hashes: dict[str, str] = {}
    stats = {"reused_files": 0, "updated_files": 0, "chunks": 0}

    md_files = sorted(knowledge_dir.glob("*.md"))
    for path in md_files:
        rel = path.name
        source_hash = sha256_file(path)
        new_hashes[rel] = source_hash

        if old_hashes.get(rel) == source_hash and old_by_file.get(rel):
            new_rows.extend(old_by_file[rel])
            stats["reused_files"] += 1
            continue

        content = path.read_text(encoding="utf-8", errors="ignore")
        doc_id = path.stem
        category = infer_category(path)
        pieces = split_markdown(content, max_chars=max_chars)

        for idx, (title, chunk_text) in enumerate(pieces, start=1):
            chunk_hash = sha256_text(f"{rel}:{idx}:{chunk_text}")[:16]
            chunk = KnowledgeChunk(
                chunk_id=f"{domain_id}:{doc_id}:{idx:04d}:{chunk_hash}",
                domain_id=domain_id,
                doc_id=doc_id,
                source_file=rel,
                source_hash=source_hash,
                title=title,
                content=chunk_text,
                category=category,
                version="v1",
                enabled=True,
                updated_at=now_str(),
            )
            new_rows.append(asdict(chunk))

        stats["updated_files"] += 1

    stats["chunks"] = len(new_rows)
    save_jsonl(chunks_file, new_rows)

    manifest = {
        "domain_id": domain_id,
        "knowledge_dir": str(knowledge_dir),
        "chunks_file": str(chunks_file),
        "file_hashes": new_hashes,
        "stats": stats,
        "updated_at": now_str(),
    }
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return manifest


def load_chunks(chunks_file: Path) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for row in load_jsonl(chunks_file):
        try:
            chunks.append(KnowledgeChunk(**row))
        except Exception:
            continue
    return chunks


def simple_search_chunks(chunks_file: Path, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
    words = [w for w in re.split(r"\s+", query.strip()) if w]
    if not words:
        # 中文场景下没有空格时，退化成按字符/整句匹配。
        words = [query.strip()]

    scored: list[tuple[float, KnowledgeChunk]] = []
    for chunk in load_chunks(chunks_file):
        if not chunk.enabled:
            continue
        text = f"{chunk.title}\n{chunk.content}"
        score = 0.0
        for word in words:
            if word and word in text:
                score += len(word)
        # 中文整句匹配弱，补充一些关键词匹配。
        for keyword in ["不回充", "不出水", "开机", "吸力", "建图", "保养", "选购", "维修"]:
            if keyword in query and keyword in text:
                score += 5
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "chunk_id": chunk.chunk_id,
            "title": chunk.title,
            "content": chunk.content,
            "category": chunk.category,
            "source_file": chunk.source_file,
            "score": score,
        }
        for score, chunk in scored[:top_k]
    ]
