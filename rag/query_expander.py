from __future__ import annotations

try:
    from agent.domain_loader import get_domain_keywords
except Exception:
    def get_domain_keywords(group: str | None = None) -> list[str]:
        return []

import re

CATEGORY_HINTS = {
    "耳机": "数码配件", "手机": "数码配件", "电脑": "数码配件", "充电器": "数码配件",
    "扫地机器人": "家用电器", "机器人": "家用电器", "冰箱": "家用电器", "洗衣机": "家用电器",
    "牛排": "生鲜食品", "水果": "生鲜食品", "海鲜": "生鲜食品",
    "会员": "虚拟商品", "兑换码": "虚拟商品", "充值": "虚拟商品",
}

INTENT_EXPANSIONS = {
    "退货": ["七天无理由", "包装完整", "不影响二次销售", "退货政策"],
    "退款": ["退款流程", "退款进度", "人工审核", "退款政策"],
    "换货": ["换货规则", "库存", "质量问题", "换货政策"],
    "维修": ["维修规则", "保修", "故障", "售后维修"],
    "质量": ["质量问题", "凭证", "照片", "人工审核"],
    "坏": ["质量问题", "故障", "无法使用", "人工审核"],
    "破损": ["质量问题", "物流破损", "凭证", "人工审核"],
    "拆封": ["已拆封", "包装完整", "二次销售", "无理由退货"],
    "无理由": ["七天无理由", "特殊商品", "包装完整", "不影响二次销售"],
    "人工": ["人工审核", "高风险订单", "质量争议", "赔付"],
    "催发货": ["订单状态", "未发货", "仓库处理", "催发货"],
    "取消订单": ["订单状态", "未发货", "已发货", "取消订单"],
}


def infer_category(query: str) -> str | None:
    for keyword, category in CATEGORY_HINTS.items():
        if keyword in query:
            return category
    return None


def expand_query(query: str, *, max_queries: int = 5) -> list[str]:
    query = (query or "").strip()
    if not query:
        return []

    queries: list[str] = [query]
    category = infer_category(query)

    if category:
        queries.append(f"{category} {query}")

    expansion_terms: list[str] = []
    for keyword, expansions in INTENT_EXPANSIONS.items():
        if keyword in query:
            expansion_terms.extend(expansions)

    seen = set()
    expansion_terms = [x for x in expansion_terms if not (x in seen or seen.add(x))]

    if expansion_terms:
        queries.append(f"{query} {' '.join(expansion_terms[:5])}")

    if category and expansion_terms:
        queries.append(f"{category} {' '.join(expansion_terms[:6])}")

    if re.search(r"能.*退|可以.*退|能不能.*退|可不可以.*退", query):
        queries.append(f"{category or ''} 七天无理由 退货 条件 包装完整 特殊商品".strip())

    if re.search(r"钱.*退|退款.*到哪|退款.*进度", query):
        queries.append("退款进度 退款流程 售后工单 审核")

    result: list[str] = []
    seen_query = set()
    for item in queries:
        item = item.strip()
        if item and item not in seen_query:
            result.append(item)
            seen_query.add(item)

    return result[:max_queries]
