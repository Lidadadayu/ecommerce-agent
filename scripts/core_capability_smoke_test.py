from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    print("1. Context Builder + Answer Guard")
    from agent.core_pipeline import finalize_answer_with_core_engineering

    route = {
        "intent": "robot_vacuum_diagnosis",
        "tool_name": "robot_vacuum_diagnosis",
        "arguments": {"query": "机器人有烧焦味还能继续用吗"},
        "error": None,
    }
    tool_result = {
        "success": True,
        "tool_name": "robot_vacuum_diagnosis",
        "message": "工具调用成功",
        "result": {
            "success": True,
            "fault_name": "高风险故障",
            "risk_level": "high",
            "safety_notice": "建议立即停止使用，不要继续充电或自行拆机，并联系售后检测。",
        },
    }
    draft = "可以继续充电观察一下，如果不行再自行拆机看看。"
    out = finalize_answer_with_core_engineering(
        user_query="机器人有烧焦味还能继续用吗",
        draft_answer=draft,
        route=route,
        tool_result=tool_result,
    )
    print(json.dumps({"final_answer": out["final_answer"], "guard_issues": out["guard_issues"]}, ensure_ascii=False, indent=2))

    print("\n2. Long Term Memory")
    from agent.long_term_memory import LongTermMemoryStore, build_user_profile_text, update_long_term_memory_from_text

    with tempfile.TemporaryDirectory() as tmp:
        store = LongTermMemoryStore(Path(tmp) / "memory.jsonl")
        update_long_term_memory_from_text(user_id="demo_user", text="我家养猫，预算3000以内，最好要自动集尘。", store=store)
        print(build_user_profile_text("demo_user", store=store))

    print("\n3. Knowledge Chunk Store")
    from agent.domain_loader import get_active_domain_config
    from rag.knowledge_chunk_store import build_knowledge_chunk_store, simple_search_chunks

    domain = get_active_domain_config()
    out_dir = PROJECT_ROOT / "data" / "runtime" / "knowledge_store" / domain.domain_id
    manifest = build_knowledge_chunk_store(knowledge_dir=domain.knowledge_dir, output_dir=out_dir, domain_id=domain.domain_id)
    print(json.dumps(manifest["stats"], ensure_ascii=False, indent=2))
    results = simple_search_chunks(out_dir / "chunks.jsonl", "扫地机器人不回充怎么办", top_k=3)
    print(json.dumps(results, ensure_ascii=False, indent=2)[:1200])


if __name__ == "__main__":
    main()
