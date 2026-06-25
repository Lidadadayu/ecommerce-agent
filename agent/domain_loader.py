from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOMAIN_PACKS_DIR = PROJECT_ROOT / "domain_packs"
DATA_KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge"

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass


DEFAULT_DOMAIN_CONFIG: dict[str, Any] = {
    "domain_id": "robot_vacuum",
    "domain_name": "扫地机器人与扫拖一体机器人",
    "project_title": "面向电商售前与售后场景的可配置 Agentic RAG 智能业务 Agent 系统",
    "demo_title": "扫地机器人售前售后一体化智能客服 Agent",
    "description": "当前领域包面向扫地机器人与扫拖一体机器人。",
    "supported_intents": [
        "robot_vacuum_search",
        "robot_vacuum_detail",
        "robot_vacuum_compare",
        "robot_vacuum_knowledge_query",
        "robot_vacuum_diagnosis",
        "policy_query",
        "aftersale_check",
        "ticket_create",
        "order_query",
        "purchase_history",
        "logistics_query",
    ],
    "knowledge_categories": {
        "robot_vacuum_troubleshooting": "故障检测与修复",
        "robot_vacuum_faq": "基础问答",
        "robot_vacuum_mop_faq": "扫拖一体问答",
        "robot_vacuum_maintenance": "维护保养",
        "robot_vacuum_buying_guide": "选购指南",
        "robot_vacuum_aftersale_policy": "售后政策",
    },
    "keywords": {
        "product_words": [
            "扫地机器人", "扫拖一体", "扫拖机器人", "机器人", "基站", "尘盒", "水箱",
            "拖布", "边刷", "主刷", "滚刷", "尘袋", "滤网", "激光雷达", "雷达", "LDS", "VSLAM",
        ],
        "presales_words": [
            "推荐", "怎么选", "选购", "买哪款", "适合", "预算", "价格", "多少钱", "参数",
            "对比", "区别", "哪个好", "大户型", "小户型", "养宠", "宠物", "猫", "狗",
            "吸力", "续航", "避障", "自动集尘", "自动洗拖布", "热风烘干", "全能基站",
        ],
        "fault_words": [
            "故障", "坏了", "怎么办", "不动", "不启动", "无法启动", "开机无反应",
            "自动关机", "不回充", "回充失败", "找不到基站", "建图失败", "地图丢失",
            "雷达异常", "原地打转", "卡住", "吸力变小", "噪音", "异响", "不出水",
            "拖地不出水", "漏水", "边刷不转", "主刷不转", "滚刷缠绕", "APP连接不上",
            "无法连接", "维修", "修复", "检测",
        ],
        "maintenance_words": [
            "保养", "维护", "清理", "清洁", "多久换", "更换周期", "耗材", "滤网",
            "尘袋", "拖布", "边刷", "主刷", "长期存放",
        ],
        "aftersales_words": [
            "保修", "售后", "退货", "退款", "换货", "维修政策", "免费维修",
            "人工审核", "赔偿", "赔付",
        ],
    },
    "prompt_rules": [
        "回答售前问题时，优先结合商品参数、使用场景和选购指南，不要虚构不存在的型号。",
        "回答故障问题时，先给出安全提醒，再按“现象判断—自查步骤—处理建议—是否建议售后”的结构回答。",
        "涉及拆机、电池鼓包、主板故障、进水、异响严重、充电异常时，应建议停止使用并联系售后。",
        "涉及退款、换货、赔付、维修是否免费时，不能承诺一定成功，应说明以订单状态、保修规则和人工审核为准。",
    ],
}


@dataclass(frozen=True)
class ActiveDomain:
    domain_id: str
    domain_name: str
    project_title: str
    demo_title: str
    description: str
    supported_intents: list[str]
    knowledge_categories: dict[str, str]
    keywords: dict[str, list[str]]
    prompt_rules: list[str]
    raw_config: dict[str, Any]

    @property
    def pack_dir(self) -> Path:
        return DOMAIN_PACKS_DIR / self.domain_id

    @property
    def products_file(self) -> Path:
        return self.pack_dir / "products.json"

    @property
    def knowledge_dir(self) -> Path:
        domain_dir = DATA_KNOWLEDGE_DIR / self.domain_id
        return domain_dir if domain_dir.exists() else DATA_KNOWLEDGE_DIR


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.lower() in {"null", "none"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def _minimal_yaml_load(text: str) -> dict[str, Any]:
    """
    兜底 YAML 解析器，只支持本项目 domain_config.yaml / prompt.yaml 的常见结构：
    - 顶层 key: value
    - 顶层 key: 下的 list
    - 顶层 key: 下的一层 mapping
    - keywords: 下的 keyword_group: [list]
    - description: > 形式的折叠文本
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    result: dict[str, Any] = {}
    i = 0

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        if not raw.startswith(" ") and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            if value == ">":
                i += 1
                collected: list[str] = []
                while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                    if lines[i].strip():
                        collected.append(lines[i].strip())
                    i += 1
                result[key] = " ".join(collected).strip()
                continue

            if value:
                result[key] = _parse_scalar(value)
                i += 1
                continue

            # 读取子块
            i += 1
            child_lines: list[str] = []
            while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                if lines[i].strip():
                    child_lines.append(lines[i])
                i += 1

            if not child_lines:
                result[key] = {}
                continue

            first = child_lines[0].strip()
            if first.startswith("- "):
                result[key] = [line.strip()[2:].strip() for line in child_lines if line.strip().startswith("- ")]
                continue

            child_dict: dict[str, Any] = {}
            j = 0
            while j < len(child_lines):
                line = child_lines[j]
                s = line.strip()

                if not s or ":" not in s:
                    j += 1
                    continue

                child_key, child_value = s.split(":", 1)
                child_key = child_key.strip()
                child_value = child_value.strip()

                if child_value:
                    child_dict[child_key] = _parse_scalar(child_value)
                    j += 1
                    continue

                # 读取孙级 list
                j += 1
                grand_list: list[str] = []
                while j < len(child_lines) and child_lines[j].startswith("    "):
                    gs = child_lines[j].strip()
                    if gs.startswith("- "):
                        grand_list.append(gs[2:].strip())
                    j += 1

                child_dict[child_key] = grand_list

            result[key] = child_dict
            continue

        i += 1

    return result


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")

    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return _minimal_yaml_load(text)


def _merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            nested = dict(result[key])
            for n_key, n_value in value.items():
                nested[n_key] = n_value
            result[key] = nested
        else:
            result[key] = value

    return result


def _normalize_keywords(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return DEFAULT_DOMAIN_CONFIG["keywords"]

    result: dict[str, list[str]] = {}

    for key, words in value.items():
        if isinstance(words, str):
            result[key] = [w.strip() for w in words.split(",") if w.strip()]
        elif isinstance(words, list):
            result[key] = [str(w).strip() for w in words if str(w).strip()]
        else:
            result[key] = []

    return result


def get_active_domain_id() -> str:
    return (os.getenv("ACTIVE_DOMAIN") or "robot_vacuum").strip() or "robot_vacuum"


@lru_cache(maxsize=8)
def load_domain_config(domain_id: str | None = None) -> ActiveDomain:
    domain_id = (domain_id or get_active_domain_id()).strip() or "robot_vacuum"
    config_path = DOMAIN_PACKS_DIR / domain_id / "domain_config.yaml"

    raw = _load_yaml_file(config_path)
    merged = _merge_config(DEFAULT_DOMAIN_CONFIG, raw)
    merged["domain_id"] = str(merged.get("domain_id") or domain_id)

    keywords = _normalize_keywords(merged.get("keywords"))

    return ActiveDomain(
        domain_id=str(merged.get("domain_id") or domain_id),
        domain_name=str(merged.get("domain_name") or domain_id),
        project_title=str(merged.get("project_title") or DEFAULT_DOMAIN_CONFIG["project_title"]),
        demo_title=str(merged.get("demo_title") or merged.get("domain_name") or domain_id),
        description=str(merged.get("description") or ""),
        supported_intents=list(merged.get("supported_intents") or []),
        knowledge_categories=dict(merged.get("knowledge_categories") or {}),
        keywords=keywords,
        prompt_rules=[str(x) for x in (merged.get("prompt_rules") or [])],
        raw_config=merged,
    )


def get_active_domain_config() -> ActiveDomain:
    return load_domain_config(get_active_domain_id())


def get_domain_keywords(group: str | None = None) -> list[str]:
    config = get_active_domain_config()
    if group:
        return list(config.keywords.get(group) or [])

    words: list[str] = []
    for items in config.keywords.values():
        words.extend(items)

    seen: set[str] = set()
    return [word for word in words if not (word in seen or seen.add(word))]


def get_domain_knowledge_dir() -> Path:
    return get_active_domain_config().knowledge_dir


def get_domain_products_file() -> Path:
    return get_active_domain_config().products_file


def get_domain_prompt_rules_text() -> str:
    rules = get_active_domain_config().prompt_rules
    if not rules:
        return ""
    return "\n".join(f"{idx}. {rule}" for idx, rule in enumerate(rules, start=1))


def clear_domain_config_cache() -> None:
    load_domain_config.cache_clear()
