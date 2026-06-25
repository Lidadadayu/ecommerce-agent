from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_ROOT = PROJECT_ROOT / "data" / "runtime" / "uploads"
ORDER_SCREENSHOT_DIR = UPLOAD_ROOT / "order_screenshots"
RECORDS_FILE = UPLOAD_ROOT / "upload_records.jsonl"

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return datetime.now().strftime("%Y%m%d")


def safe_filename(filename: str | None) -> str:
    raw = filename or "upload.png"
    raw = raw.replace("\\", "_").replace("/", "_").strip()
    raw = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fa5]+", "_", raw)
    return raw[:120] or "upload.png"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@dataclass
class EvidenceRecord:
    evidence_id: str
    evidence_type: str
    customer_id: str
    session_id: str | None
    order_id: str | None
    original_filename: str
    stored_filename: str
    file_path: str
    content_type: str | None
    size_bytes: int
    sha256: str
    note: str | None = None
    created_at: str = field(default_factory=now_str)


def _ensure_dirs() -> None:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    ORDER_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _load_records() -> list[dict[str, Any]]:
    if not RECORDS_FILE.exists():
        return []

    rows: list[dict[str, Any]] = []
    for line in RECORDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except Exception:
            continue
    return rows


def _append_record(record: EvidenceRecord) -> None:
    _ensure_dirs()
    with RECORDS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def save_order_screenshot(
    *,
    content: bytes,
    filename: str,
    customer_id: str,
    session_id: str | None = None,
    order_id: str | None = None,
    content_type: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """
    保存订单截图凭证。

    当前只做上传、存储、登记，不做 OCR。
    后续人工审核后台可通过 evidence_id 查看文件。
    """

    _ensure_dirs()

    if not customer_id:
        raise ValueError("customer_id 不能为空。")

    if not content:
        raise ValueError("上传文件为空。")

    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"文件过大，最大支持 {MAX_UPLOAD_BYTES // 1024 // 1024}MB。")

    original = safe_filename(filename)
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f"当前只支持订单截图图片格式：{', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}。")

    evidence_id = f"EV{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
    digest = sha256_bytes(content)

    customer_dir = ORDER_SCREENSHOT_DIR / customer_id / today_str()
    customer_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{evidence_id}{ext}"
    file_path = customer_dir / stored_filename
    file_path.write_bytes(content)

    record = EvidenceRecord(
        evidence_id=evidence_id,
        evidence_type="order_screenshot",
        customer_id=customer_id,
        session_id=session_id,
        order_id=order_id or None,
        original_filename=original,
        stored_filename=stored_filename,
        file_path=str(file_path.relative_to(PROJECT_ROOT)),
        content_type=content_type,
        size_bytes=len(content),
        sha256=digest,
        note=(note or "").strip() or None,
    )
    _append_record(record)

    data = asdict(record)
    data["file_url"] = f"/api/uploads/files/{evidence_id}"
    return data


def list_evidences(
    *,
    customer_id: str | None = None,
    session_id: str | None = None,
    order_id: str | None = None,
    evidence_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = _load_records()

    if customer_id:
        rows = [r for r in rows if str(r.get("customer_id")) == str(customer_id)]

    if session_id:
        rows = [r for r in rows if str(r.get("session_id")) == str(session_id)]

    if order_id:
        rows = [r for r in rows if str(r.get("order_id")) == str(order_id)]

    if evidence_type:
        rows = [r for r in rows if str(r.get("evidence_type")) == str(evidence_type)]

    rows.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)

    safe_limit = max(1, min(int(limit or 50), 200))
    for row in rows[:safe_limit]:
        if row.get("evidence_id"):
            row["file_url"] = f"/api/uploads/files/{row['evidence_id']}"
    return rows[:safe_limit]


def get_evidence(evidence_id: str) -> dict[str, Any] | None:
    for row in _load_records():
        if row.get("evidence_id") == evidence_id:
            row["file_url"] = f"/api/uploads/files/{evidence_id}"
            return row
    return None


def resolve_evidence_path(evidence_id: str) -> Path | None:
    row = get_evidence(evidence_id)
    if not row:
        return None

    rel = row.get("file_path")
    if not rel:
        return None

    path = (PROJECT_ROOT / rel).resolve()
    root = UPLOAD_ROOT.resolve()

    # 防止路径穿越。
    try:
        path.relative_to(root)
    except ValueError:
        return None

    if not path.exists() or not path.is_file():
        return None

    return path


def summarize_evidences(evidences: list[dict[str, Any]]) -> str:
    if not evidences:
        return "暂无上传凭证。"

    lines = [f"已上传 {len(evidences)} 个订单截图凭证："]
    for item in evidences[:5]:
        lines.append(
            f"- {item.get('evidence_id')}：{item.get('original_filename')}，"
            f"订单号：{item.get('order_id') or '未填写'}，时间：{item.get('created_at')}"
        )
    return "\n".join(lines)
