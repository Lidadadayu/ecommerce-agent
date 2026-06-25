from __future__ import annotations

import json
import sys
import time
import traceback
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class CheckResult:
    name: str
    ok: bool
    required: bool
    detail: str
    elapsed_ms: float = 0.0


RESULTS: list[CheckResult] = []


def _now_ms() -> float:
    return time.perf_counter() * 1000


def add_result(name: str, ok: bool, detail: str, *, required: bool = True, elapsed_ms: float = 0.0) -> None:
    RESULTS.append(CheckResult(name=name, ok=ok, required=required, detail=detail, elapsed_ms=round(elapsed_ms, 2)))


def run_check(name: str, func: Callable[[], tuple[bool, str]], *, required: bool = True) -> None:
    start = _now_ms()
    try:
        ok, detail = func()
    except Exception as exc:
        ok = False
        detail = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=2)}"
    add_result(name, ok, detail, required=required, elapsed_ms=_now_ms() - start)


def check_domain() -> tuple[bool, str]:
    from agent.domain_loader import get_active_domain_config

    d = get_active_domain_config()
    ok = d.domain_id == "robot_vacuum" and d.products_file.exists() and d.knowledge_dir.exists()
    detail = {
        "domain_id": d.domain_id,
        "domain_name": d.domain_name,
        "products_file": str(d.products_file),
        "knowledge_dir": str(d.knowledge_dir),
        "products_exists": d.products_file.exists(),
        "knowledge_dir_exists": d.knowledge_dir.exists(),
    }
    return ok, json.dumps(detail, ensure_ascii=False)


def check_tool_registry() -> tuple[bool, str]:
    from tools.tool_registry import TOOL_REGISTRY

    required_tools = [
        "robot_vacuum_search",
        "robot_vacuum_detail",
        "robot_vacuum_compare",
        "robot_vacuum_knowledge_query",
        "robot_vacuum_diagnosis",
        "order_query",
        "logistics_query",
        "aftersale_check",
        "ticket_create",
    ]
    missing = [name for name in required_tools if name not in TOOL_REGISTRY]
    return not missing, f"tool_count={len(TOOL_REGISTRY)}, missing={missing}"


def check_router() -> tuple[bool, str]:
    from agent.rule_router import route_user_query

    cases = {
        "3000以内推荐一款扫拖一体机器人": "robot_vacuum_search",
        "RV4001 参数怎么样": "robot_vacuum_detail",
        "对比 RV2001 和 RV4001": "robot_vacuum_compare",
        "扫地机器人不回充怎么办": "robot_vacuum_diagnosis",
        "机器人有烧焦味还能继续用吗": "robot_vacuum_diagnosis",
    }

    errors = []
    for query, expected in cases.items():
        route = route_user_query(query)
        actual = route.get("intent")
        if actual != expected:
            errors.append({"query": query, "expected": expected, "actual": actual, "route": route})

    return not errors, json.dumps(errors, ensure_ascii=False)


def check_rag() -> tuple[bool, str]:
    from rag.rag_service import retrieve_knowledge

    result = retrieve_knowledge("扫地机器人不回充怎么办", top_k=3)
    titles = [item.get("title") for item in result[:3]]
    return len(result) > 0, f"count={len(result)}, titles={titles}"


def _run_agent_once(query: str, memory: dict[str, Any] | None = None) -> dict[str, Any]:
    from agent.agent import run_agent

    result = run_agent(query, memory=memory)
    if not isinstance(result, dict):
        return {"final_answer": str(result), "memory": memory or {}}
    return result


def check_presales_flow() -> tuple[bool, str]:
    queries = [
        "3000以内推荐一款扫拖一体机器人",
        "RV4001 参数怎么样",
        "对比 RV2001 和 RV4001",
    ]

    memory = None
    previews = []

    for query in queries:
        result = _run_agent_once(query, memory=memory)
        memory = result.get("memory")
        answer = str(result.get("final_answer") or "")
        previews.append({"query": query, "intent": result.get("intent"), "preview": answer[:120]})
        if not answer.strip():
            return False, json.dumps(previews, ensure_ascii=False)

    return True, json.dumps(previews, ensure_ascii=False)


def check_diagnosis_flow() -> tuple[bool, str]:
    queries = [
        "扫地机器人不回充怎么办",
        "扫拖一体机器人拖地不出水怎么办",
        "机器人有烧焦味还能继续用吗",
    ]

    previews = []
    for query in queries:
        result = _run_agent_once(query)
        answer = str(result.get("final_answer") or "")
        previews.append({"query": query, "intent": result.get("intent"), "tool": result.get("tool_name"), "preview": answer[:180]})

        if not answer.strip():
            return False, json.dumps(previews, ensure_ascii=False)

        if "烧焦" in query and not any(word in answer for word in ["停止使用", "不要继续充电", "售后", "检测"]):
            return False, json.dumps(previews, ensure_ascii=False)

    return True, json.dumps(previews, ensure_ascii=False)


def check_memory_flow_optional() -> tuple[bool, str]:
    """
    订单和物流依赖数据库。数据库没有初始化时该项允许失败。
    """

    memory = None
    steps = []

    for query in ["帮我查一下 O202605010001 这个订单", "物流到哪了？", "这个订单可以维修吗？"]:
        result = _run_agent_once(query, memory=memory)
        memory = result.get("memory")
        answer = str(result.get("final_answer") or "")
        steps.append(
            {
                "query": query,
                "intent": result.get("intent"),
                "tool": result.get("tool_name"),
                "preview": answer[:160],
            }
        )

    text = json.dumps(steps, ensure_ascii=False)
    ok = any("O202605010001" in str(step) for step in steps)
    return ok, text


def check_api_import() -> tuple[bool, str]:
    from api.server import app

    routes = sorted([route.path for route in app.routes])
    needed = ["/api/health", "/api/domain", "/api/chat", "/api/logs/recent"]
    missing = [path for path in needed if path not in routes]
    return not missing, f"missing={missing}, route_count={len(routes)}"


def print_report() -> int:
    print()
    print("=" * 88)
    print("系统验收流程测试结果")
    print("=" * 88)

    for item in RESULTS:
        mark = "✅" if item.ok else ("⚠️" if not item.required else "❌")
        req = "required" if item.required else "optional"
        print(f"{mark} {item.name} [{req}] {item.elapsed_ms}ms")
        print(f"   {item.detail}")

    required_failed = [item for item in RESULTS if item.required and not item.ok]
    passed = sum(1 for item in RESULTS if item.ok)
    total = len(RESULTS)

    print()
    print(f"Summary: {passed}/{total} passed")
    if required_failed:
        print("Required failed:", [item.name for item in required_failed])
    else:
        print("All required checks passed.")

    output_dir = PROJECT_ROOT / "data" / "runtime" / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "acceptance_flow_test.json"
    output_file.write_text(
        json.dumps([asdict(item) for item in RESULTS], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Report saved: {output_file}")

    return 1 if required_failed else 0


def main() -> None:
    run_check("领域包加载", check_domain)
    run_check("工具注册表", check_tool_registry)
    run_check("规则路由", check_router)
    run_check("RAG 检索", check_rag)
    run_check("售前流程", check_presales_flow)
    run_check("故障诊断流程", check_diagnosis_flow)
    run_check("API 模块", check_api_import)
    run_check("订单/物流/售后多轮流程", check_memory_flow_optional, required=False)

    raise SystemExit(print_report())


if __name__ == "__main__":
    main()
