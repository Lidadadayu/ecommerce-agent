from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MEMORY_PATH = PROJECT_ROOT / "data" / "runtime" / "memory" / "long_term_memory.jsonl"


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class LongTermMemoryItem:
    user_id: str
    memory_type: str
    key: str
    value: Any
    source: str = "conversation"
    confidence: float = 0.7
    created_at: str = field(default_factory=now_str)
    updated_at: str = field(default_factory=now_str)
    enabled: bool = True


class LongTermMemoryStore:
    """
    简单 JSONL 长期记忆存储。

    适合课程/演示项目，不依赖外部数据库。
    后续如果要生产化，可以替换为 PostgreSQL / Redis / 向量库。
    """

    def __init__(self, path: Path | str = DEFAULT_MEMORY_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> list[LongTermMemoryItem]:
        if not self.path.exists():
            return []

        items: list[LongTermMemoryItem] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                items.append(LongTermMemoryItem(**data))
            except Exception:
                continue
        return items

    def save_all(self, items: list[LongTermMemoryItem]) -> None:
        text = "\n".join(json.dumps(asdict(item), ensure_ascii=False) for item in items)
        self.path.write_text(text + ("\n" if text else ""), encoding="utf-8")

    def upsert(
        self,
        *,
        user_id: str,
        memory_type: str,
        key: str,
        value: Any,
        source: str = "conversation",
        confidence: float = 0.7,
    ) -> LongTermMemoryItem:
        items = self.load_all()
        now = now_str()

        for item in items:
            if item.user_id == user_id and item.memory_type == memory_type and item.key == key and item.enabled:
                item.value = value
                item.source = source
                item.confidence = confidence
                item.updated_at = now
                self.save_all(items)
                return item

        item = LongTermMemoryItem(
            user_id=user_id,
            memory_type=memory_type,
            key=key,
            value=value,
            source=source,
            confidence=confidence,
        )
        items.append(item)
        self.save_all(items)
        return item

    def query(self, *, user_id: str, memory_type: str | None = None, limit: int = 20) -> list[LongTermMemoryItem]:
        items = [item for item in self.load_all() if item.user_id == user_id and item.enabled]
        if memory_type:
            items = [item for item in items if item.memory_type == memory_type]
        items.sort(key=lambda x: x.updated_at, reverse=True)
        return items[:limit]

    def disable(self, *, user_id: str, memory_type: str, key: str) -> bool:
        items = self.load_all()
        changed = False
        for item in items:
            if item.user_id == user_id and item.memory_type == memory_type and item.key == key and item.enabled:
                item.enabled = False
                item.updated_at = now_str()
                changed = True
        if changed:
            self.save_all(items)
        return changed


def extract_memory_candidates(text: str) -> list[dict[str, Any]]:
    """
    从用户输入中抽取可长期保存的低敏偏好。

    这里故意只抽取业务偏好，不保存敏感信息。
    """

    candidates: list[dict[str, Any]] = []

    if any(word in text for word in ["养宠", "宠物", "猫", "狗", "毛发"]):
        candidates.append({"memory_type": "preference", "key": "pet_family", "value": True, "confidence": 0.8})

    budget_match = re.search(r"(?:预算|不超过|以内|以下)\s*(\d{3,5})", text)
    if budget_match:
        budget = int(budget_match.group(1))
        if 300 <= budget <= 20000:
            candidates.append({"memory_type": "preference", "key": "budget_max", "value": budget, "confidence": 0.75})

    if any(word in text for word in ["自动集尘", "集尘"]):
        candidates.append({"memory_type": "preference", "key": "need_auto_dust", "value": True, "confidence": 0.75})

    if any(word in text for word in ["自动洗拖布", "洗拖布", "全能基站"]):
        candidates.append({"memory_type": "preference", "key": "need_auto_mop_wash", "value": True, "confidence": 0.75})

    if any(word in text for word in ["大户型", "面积大", "120平", "150平", "180平"]):
        candidates.append({"memory_type": "preference", "key": "large_house", "value": True, "confidence": 0.65})

    return candidates


def update_long_term_memory_from_text(
    *,
    user_id: str,
    text: str,
    store: LongTermMemoryStore | None = None,
) -> list[LongTermMemoryItem]:
    store = store or LongTermMemoryStore()
    saved: list[LongTermMemoryItem] = []

    for candidate in extract_memory_candidates(text):
        saved.append(
            store.upsert(
                user_id=user_id,
                memory_type=candidate["memory_type"],
                key=candidate["key"],
                value=candidate["value"],
                source="conversation",
                confidence=candidate["confidence"],
            )
        )

    return saved


def build_user_profile_text(user_id: str, store: LongTermMemoryStore | None = None) -> str:
    store = store or LongTermMemoryStore()
    items = store.query(user_id=user_id, memory_type="preference", limit=20)
    if not items:
        return ""

    lines = ["用户长期偏好："]
    for item in items:
        lines.append(f"- {item.key}: {item.value}（confidence={item.confidence}）")
    return "\n".join(lines)
