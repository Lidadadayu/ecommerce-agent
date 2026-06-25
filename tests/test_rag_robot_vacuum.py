from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge" / "robot_vacuum"


def _skip_if_no_robot_knowledge():
    if not KNOWLEDGE_DIR.exists() or not list(KNOWLEDGE_DIR.glob("*.md")):
        pytest.skip("robot_vacuum 知识库尚未导入，请先运行 python scripts/import_robot_vacuum_knowledge.py")


def test_robot_vacuum_rag_retrieve():
    _skip_if_no_robot_knowledge()

    from rag.rag_service import retrieve_knowledge

    result = retrieve_knowledge("扫地机器人不回充怎么办", top_k=3)

    assert len(result) > 0
    text = "\n".join(str(item.get("title", "")) + str(item.get("content", "")) for item in result)
    assert any(word in text for word in ["回充", "机器人", "故障", "充电", "基站"])


def test_robot_vacuum_rag_context():
    _skip_if_no_robot_knowledge()

    from rag.rag_service import build_rag_context

    context = build_rag_context("扫地机器人不回充怎么办")

    assert "知识库检索结果" in context
    assert any(word in context for word in ["回充", "机器人", "故障", "充电", "基站"])
