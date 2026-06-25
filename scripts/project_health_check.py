from __future__ import annotations

import importlib
import json
import sys
import traceback
import warnings
from pathlib import Path
from typing import Any


warnings.filterwarnings(
    "ignore",
    message=r".*allowed_objects.*",
    category=Warning,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


CHECK_RESULTS: list[dict[str, Any]] = []


def _mark(name: str, ok: bool, detail: str = "", suggestion: str = "") -> None:
    CHECK_RESULTS.append(
        {
            "name": name,
            "ok": ok,
            "detail": detail,
            "suggestion": suggestion,
        }
    )


def _print_section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def check_python_version() -> None:
    version = sys.version_info
    ok = version.major == 3 and version.minor >= 10
    _mark(
        "Python 版本",
        ok,
        f"{version.major}.{version.minor}.{version.micro}",
        "建议使用 Python 3.10+，当前项目你使用 py312 是可以的。",
    )


def check_project_root() -> None:
    required = ["agent", "tools", "rag", "database", "domain_packs", "data", "app.py"]
    missing = [x for x in required if not (PROJECT_ROOT / x).exists()]
    _mark(
        "项目根目录",
        not missing,
        f"PROJECT_ROOT={PROJECT_ROOT}; missing={missing}",
        "请在 ecommerce_agent 项目根目录运行该脚本：python scripts/project_health_check.py",
    )


def check_imports() -> None:
    modules = [
        "agent.agent",
        "agent.domain_loader",
        "agent.rule_router",
        "agent.domain_guard",
        "agent.memory",
        "tools.tool_registry",
        "tools.robot_vacuum_tools",
        "rag.rag_service",
        "database.db",
    ]

    for module in modules:
        try:
            importlib.import_module(module)
            _mark(f"模块导入：{module}", True, "ok")
        except Exception as exc:
            _mark(
                f"模块导入：{module}",
                False,
                f"{type(exc).__name__}: {exc}",
                "检查文件是否存在、补丁是否覆盖完整，以及是否在项目根目录运行。",
            )


def check_active_domain() -> None:
    try:
        from agent.domain_loader import get_active_domain_config

        domain = get_active_domain_config()
        detail = {
            "domain_id": domain.domain_id,
            "domain_name": domain.domain_name,
            "products_file": str(domain.products_file),
            "knowledge_dir": str(domain.knowledge_dir),
            "products_exists": domain.products_file.exists(),
            "knowledge_dir_exists": domain.knowledge_dir.exists(),
        }

        ok = domain.products_file.exists() and domain.knowledge_dir.exists()
        _mark(
            "领域包加载",
            ok,
            json.dumps(detail, ensure_ascii=False),
            "检查 .env 中 ACTIVE_DOMAIN 是否正确，以及 domain_packs/ 与 data/knowledge/ 是否存在对应目录。",
        )

    except Exception as exc:
        _mark(
            "领域包加载",
            False,
            f"{type(exc).__name__}: {exc}",
            "检查 agent/domain_loader.py 和 domain_packs/robot_vacuum/domain_config.yaml。",
        )


def check_robot_products() -> None:
    try:
        from tools.robot_vacuum_tools import search_robot_vacuum_products

        result = search_robot_vacuum_products("养宠家庭怎么选扫地机器人", pet_family=True)
        count = int(result.get("count") or 0)
        _mark(
            "扫地机器人商品工具",
            count > 0,
            f"count={count}; message={result.get('message')}",
            "检查 domain_packs/robot_vacuum/products.json 是否存在且格式正确。",
        )

    except Exception as exc:
        _mark(
            "扫地机器人商品工具",
            False,
            f"{type(exc).__name__}: {exc}",
            "检查 tools/robot_vacuum_tools.py 与 products.json。",
        )


def check_tool_registry() -> None:
    try:
        from tools.tool_registry import TOOL_REGISTRY

        required_tools = [
            "robot_vacuum_search",
            "robot_vacuum_detail",
            "robot_vacuum_compare",
            "robot_vacuum_knowledge_query",
            "order_query",
            "logistics_query",
            "aftersale_check",
            "ticket_create",
        ]

        missing = [name for name in required_tools if name not in TOOL_REGISTRY]

        _mark(
            "工具注册表",
            not missing,
            f"tool_count={len(TOOL_REGISTRY)}; missing={missing}",
            "检查 tools/tool_registry.py 是否已经覆盖扫地机器人售前工具接入补丁。",
        )

    except Exception as exc:
        _mark(
            "工具注册表",
            False,
            f"{type(exc).__name__}: {exc}",
            "检查 tools/tool_registry.py。",
        )


def check_router() -> None:
    try:
        from agent.rule_router import route_user_query

        cases = {
            "养宠家庭怎么选扫地机器人": "robot_vacuum_search",
            "扫地机器人不回充怎么办": "robot_vacuum_diagnosis",
            "对比 RV2001 和 RV4001": "robot_vacuum_compare",
            "RV4001 参数怎么样": "robot_vacuum_detail",
        }

        failed = []
        for query, expected in cases.items():
            route = route_user_query(query)
            actual = route.get("intent")
            if actual != expected:
                failed.append({"query": query, "expected": expected, "actual": actual, "route": route})

        _mark(
            "规则路由",
            not failed,
            json.dumps(failed, ensure_ascii=False),
            "检查 agent/rule_router.py 是否正确接入领域关键词与扫地机器人 intent。故障类问题应优先进入 robot_vacuum_diagnosis。",
        )

    except Exception as exc:
        _mark(
            "规则路由",
            False,
            f"{type(exc).__name__}: {exc}",
            "检查 agent/rule_router.py。",
        )


def check_rag() -> None:
    try:
        from rag.rag_service import retrieve_knowledge

        result = retrieve_knowledge("扫地机器人不回充怎么办", top_k=3)
        ok = len(result) > 0

        titles = [str(item.get("title") or "") for item in result[:3]]
        _mark(
            "RAG 检索",
            ok,
            f"count={len(result)}; titles={titles}",
            "如果没有检索结果，请先运行 python scripts/import_robot_vacuum_knowledge.py，并确认 data/knowledge/robot_vacuum/ 下有 md 文件。",
        )

    except Exception as exc:
        _mark(
            "RAG 检索",
            False,
            f"{type(exc).__name__}: {exc}",
            "检查 rag/rag_service.py 与 data/knowledge/robot_vacuum/。",
        )


def check_agent_basic() -> None:
    try:
        from agent.agent import run_agent

        result = run_agent("3000以内推荐一款扫拖一体机器人")
        answer = str(result.get("final_answer") or "")
        ok = bool(answer.strip())

        _mark(
            "完整 Agent 链路",
            ok,
            f"answer_preview={answer[:160]}",
            "如果失败，检查 LangGraph、tools/tool_registry.py、agent/workflow_nodes.py 与 LLM 配置。若 LLM 未配置，系统应尽量走模板回复。",
        )

    except Exception as exc:
        _mark(
            "完整 Agent 链路",
            False,
            f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=2)}",
            "先测试 python -c \"from agent.rule_router import route_user_query; print(route_user_query('3000以内推荐一款扫拖一体机器人'))\"，再定位是路由、工具还是 LLM 问题。",
        )


def check_optional_database() -> None:
    try:
        from sqlalchemy import text
        from database.db import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        _mark("数据库连接", True, "SELECT 1 ok")

    except Exception as exc:
        _mark(
            "数据库连接",
            False,
            f"{type(exc).__name__}: {exc}",
            "数据库不是售前/RAG 演示的必需项。若要测试订单、物流、售后，请先配置 .env 中 DATABASE_URL，并运行 python database/init_db.py。",
        )


def print_report() -> int:
    _print_section("项目健康检查结果")

    ok_count = sum(1 for item in CHECK_RESULTS if item["ok"])
    total = len(CHECK_RESULTS)

    for item in CHECK_RESULTS:
        mark = "✅" if item["ok"] else "❌"
        print(f"{mark} {item['name']}")
        if item["detail"]:
            print(f"   detail: {item['detail']}")
        if (not item["ok"]) and item["suggestion"]:
            print(f"   suggestion: {item['suggestion']}")

    print()
    print(f"Summary: {ok_count}/{total} passed")

    output_dir = PROJECT_ROOT / "data" / "runtime" / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "project_health_check.json"
    output_file.write_text(json.dumps(CHECK_RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report saved: {output_file}")

    # 数据库连接失败不阻断基础演示；其他失败才返回 1。
    blocking_failed = [
        item for item in CHECK_RESULTS
        if (not item["ok"]) and item["name"] != "数据库连接"
    ]
    return 1 if blocking_failed else 0


def main() -> None:
    _print_section("正在检查项目运行环境")

    check_python_version()
    check_project_root()
    check_imports()
    check_active_domain()
    check_robot_products()
    check_tool_registry()
    check_router()
    check_rag()
    check_agent_basic()
    check_optional_database()

    raise SystemExit(print_report())


if __name__ == "__main__":
    main()
