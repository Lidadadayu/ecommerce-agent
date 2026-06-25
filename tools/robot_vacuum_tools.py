from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_products() -> list[dict[str, Any]]:
    try:
        from agent.domain_loader import get_domain_products_file

        product_file = get_domain_products_file()
    except Exception:
        product_file = PROJECT_ROOT / "domain_packs" / "robot_vacuum" / "products.json"

    if not product_file.exists():
        return []

    try:
        data = json.loads(product_file.read_text(encoding="utf-8"))
    except Exception:
        return []

    return data if isinstance(data, list) else []


def _bool_match(value: Any, expected: bool | None) -> int:
    if expected is None:
        return 0
    return 2 if bool(value) == expected else -1


def _contains_any(text: str, words: list[str]) -> bool:
    text = text or ""
    return any(word in text for word in words)


def _build_recommend_reason(product: dict[str, Any], *, query: str, pet_family: bool | None, area_min: int | None) -> list[str]:
    reasons: list[str] = []

    suction = int(product.get("suction_pa") or 0)
    if suction >= 5000:
        reasons.append(f"吸力 {suction}Pa，适合灰尘、毛发较多场景")
    elif suction >= 4000:
        reasons.append(f"吸力 {suction}Pa，日常清扫和养宠家庭基本够用")
    else:
        reasons.append(f"吸力 {suction}Pa，适合小户型日常清扫")

    if product.get("navigation"):
        reasons.append(f"导航方式：{product.get('navigation')}")

    if product.get("auto_dust_collection"):
        reasons.append("支持自动集尘，降低倒尘频率")

    if product.get("auto_mop_wash"):
        reasons.append("支持自动洗拖布，更适合拖地需求高的家庭")

    if product.get("hot_air_drying"):
        reasons.append("支持热风烘干，能减少拖布异味")

    if pet_family and "养宠家庭" in (product.get("target_users") or []):
        reasons.append("定位包含养宠家庭，适合毛发清理需求")

    if area_min is not None and product.get("suitable_area"):
        reasons.append(f"标称适用面积：{product.get('suitable_area')}")

    if not reasons and query:
        reasons.append("与当前咨询关键词匹配")

    return reasons[:4]


def search_robot_vacuum_products(
    query: str | None = None,
    *,
    budget_max: int | None = None,
    need_mop: bool | None = None,
    need_auto_dust: bool | None = None,
    need_auto_mop_wash: bool | None = None,
    pet_family: bool | None = None,
    area_min: int | None = None,
) -> dict[str, Any]:
    """
    扫地机器人售前商品搜索工具。
    第一版使用本地 JSON 数据，后续可以替换为数据库查询。
    """

    products = _load_products()
    query = (query or "").strip()

    results: list[dict[str, Any]] = []

    for product in products:
        score = 0
        text = json.dumps(product, ensure_ascii=False)

        if query and query in text:
            score += 3

        if budget_max is not None:
            price = int(product.get("price") or 0)
            score += 3 if price <= budget_max else -2

        score += _bool_match(product.get("mop"), need_mop)
        score += _bool_match(product.get("auto_dust_collection"), need_auto_dust)
        score += _bool_match(product.get("auto_mop_wash"), need_auto_mop_wash)

        if pet_family is not None:
            if pet_family and "养宠家庭" in (product.get("target_users") or []):
                score += 3
            elif pet_family:
                score -= 1

        if area_min is not None:
            suitable = str(product.get("suitable_area") or "")
            if area_min >= 150 and any(x in suitable for x in ["150", "180", "250"]):
                score += 3
            elif area_min >= 100 and any(x in suitable for x in ["120", "140", "150", "180", "250"]):
                score += 2
            elif area_min < 100:
                score += 1

        # 没有明确筛选条件时，保留所有商品，按价格和能力排序。
        if score > 0 or not any(v is not None for v in [budget_max, need_mop, need_auto_dust, need_auto_mop_wash, pet_family, area_min]):
            item = dict(product)
            item["_match_score"] = score
            item["recommend_reasons"] = _build_recommend_reason(
                product,
                query=query,
                pet_family=pet_family,
                area_min=area_min,
            )
            results.append(item)

    results.sort(key=lambda x: (x.get("_match_score", 0), x.get("suction_pa", 0), x.get("price", 0)), reverse=True)

    return {
        "success": True,
        "query": query,
        "filters": {
            "budget_max": budget_max,
            "need_mop": need_mop,
            "need_auto_dust": need_auto_dust,
            "need_auto_mop_wash": need_auto_mop_wash,
            "pet_family": pet_family,
            "area_min": area_min,
        },
        "count": len(results[:5]),
        "products": results[:5],
        "message": "已根据扫地机器人领域商品库完成检索。",
    }


def get_robot_vacuum_product_detail(product_id: str) -> dict[str, Any]:
    products = _load_products()
    product_id = (product_id or "").strip().upper()

    for product in products:
        if str(product.get("product_id")).upper() == product_id:
            return {
                "success": True,
                "product": product,
                "message": "已查询到扫地机器人商品详情。",
            }

    return {
        "success": False,
        "product_id": product_id,
        "message": f"未找到商品 {product_id}，请确认商品 ID 是否正确，例如 RV1001、RV2001、RV3001、RV4001。",
    }


def compare_robot_vacuum_products(product_ids: list[str]) -> dict[str, Any]:
    products = _load_products()
    product_ids = [str(pid).strip().upper() for pid in product_ids if str(pid).strip()]
    product_map = {str(item.get("product_id")).upper(): item for item in products}

    selected = [product_map[pid] for pid in product_ids if pid in product_map]

    if len(selected) < 2:
        return {
            "success": False,
            "message": "至少需要提供两个有效扫地机器人商品 ID 才能进行对比，例如 RV2001 和 RV4001。",
            "products": selected,
        }

    fields = [
        "price",
        "suction_pa",
        "navigation",
        "battery_mah",
        "runtime_min",
        "suitable_area",
        "mop",
        "auto_dust_collection",
        "auto_mop_wash",
        "hot_air_drying",
        "obstacle_avoidance",
        "warranty_months",
    ]

    comparison = []
    for product in selected:
        comparison.append(
            {
                "product_id": product.get("product_id"),
                "name": product.get("name"),
                **{field: product.get(field) for field in fields},
                "target_users": product.get("target_users") or [],
            }
        )

    return {
        "success": True,
        "comparison": comparison,
        "message": "已完成扫地机器人商品参数对比。",
    }


def query_robot_vacuum_knowledge(
    query: str,
    *,
    category: str | None = None,
    top_k: int = 4,
) -> dict[str, Any]:
    """
    扫地机器人领域知识查询工具。

    用于：
    - 故障排查
    - 维护保养
    - 选购知识
    - 售后政策解释
    """

    try:
        from rag.rag_service import retrieve_knowledge
    except Exception as exc:
        return {
            "success": False,
            "query": query,
            "category": category,
            "message": f"知识库检索模块不可用：{exc}",
            "chunks": [],
        }

    chunks = retrieve_knowledge(query, category=category, top_k=top_k)

    return {
        "success": True,
        "query": query,
        "category": category,
        "count": len(chunks),
        "chunks": chunks,
        "message": "已从扫地机器人领域知识库检索相关内容。",
    }
