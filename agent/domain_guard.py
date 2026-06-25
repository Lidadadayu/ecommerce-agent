from __future__ import annotations

from typing import TypedDict

from agent.domain_loader import get_active_domain_config, get_domain_keywords
from agent.patterns import ORDER_ID_PATTERN, PRODUCT_ID_PATTERN


class DomainDecision(TypedDict):
    allowed: bool
    category: str
    reason: str
    reply: str | None


GREETING_WORDS = ["你好", "您好", "hello", "hi", "在吗", "哈喽", "嗨", "客服在吗", "有人吗"]
THANKS_WORDS = ["谢谢", "感谢", "辛苦了", "好的谢谢", "明白了", "知道了"]
GOODBYE_WORDS = ["再见", "拜拜", "下次再说", "没事了", "不用了"]
IDENTITY_WORDS = ["你是谁", "你叫什么", "你是什么", "你是机器人吗", "你是客服吗", "介绍一下你自己", "介绍一下自己"]
CAPABILITY_WORDS = ["你能做什么", "你可以做什么", "有什么功能", "能帮我什么", "怎么使用", "使用说明", "帮助", "功能介绍"]
HUMAN_SERVICE_WORDS = ["人工客服", "转人工", "真人客服", "找人工", "客服人员", "人工处理"]
BASE_BUSINESS_WORDS = ["商品", "订单", "订单截图", "截图", "凭证", "图片", "物流", "快递", "发货", "签收", "配送", "售后", "退货", "退", "换货", "换", "退款", "维修", "工单", "催发货", "投诉", "退换货", "运营", "销量", "退款率", "客诉", "GMV", "库存", "价格", "耳机", "生鲜", "电子书", "数码配件", "家用电器", "服饰", "虚拟商品"]
BUSINESS_WORDS = BASE_BUSINESS_WORDS + get_domain_keywords()
OUT_OF_SCOPE_GROUPS = {
    "news": ["新闻", "热点", "时事", "国际局势", "今天发生了什么", "最新消息"],
    "finance": ["股票", "基金", "彩票", "大乐透", "投资建议", "币圈", "比特币", "收益率"],
    "medical": ["诊断", "处方", "吃什么药", "治疗方案", "病情", "医院"],
    "legal": ["起诉", "判刑", "合同纠纷", "法律意见", "律师"],
    "politics": ["总统", "选举", "政治", "外交", "政府"],
    "general_homework": ["写论文", "写作文", "历史题", "数学题", "翻译这段"],
}


def _contains_any(text: str, words: list[str]) -> bool:
    lower = text.lower()
    return any(w.lower() in lower for w in words)


def _has_business_signal(text: str) -> bool:
    return bool(ORDER_ID_PATTERN.search(text) or PRODUCT_ID_PATTERN.search(text) or _contains_any(text, BUSINESS_WORDS))


def _pure(text: str, words: list[str], max_len: int) -> bool:
    text = text.strip().lower()
    return len(text) <= max_len and _contains_any(text, words)


def build_identity_reply() -> str:
    domain = get_active_domain_config()
    return f"我是电商售后与运营 Agent 助手，当前演示领域是：{domain.domain_name}。我可以帮助你处理售前商品咨询、参数对比、故障排查、维护保养、订单查询、物流跟踪、售后政策解释、退货/换货/维修资格预判断和售后工单生成。涉及高价值商品、特殊类目、质量争议或退款赔付时，我会提示需要人工客服审核。"


def build_greeting_reply() -> str:
    domain = get_active_domain_config()
    return f"你好，我是电商售后与运营 Agent 助手。当前领域：{domain.domain_name}。你可以让我帮你做商品咨询、型号对比、故障排查、查订单、查物流、看售后政策，或者判断某个订单是否可以退货、换货或维修。"


def build_thanks_reply() -> str:
    return "不客气，很高兴帮到你。如果还需要查询订单、物流、售后工单或退换货规则，可以继续告诉我。"


def build_goodbye_reply() -> str:
    return "好的，后续如果还有商品、订单、物流或售后问题，随时可以再来找我。"


def build_human_service_reply() -> str:
    return "可以的。如果问题涉及退款赔付、质量争议、高价值商品、特殊类目或对规则判断结果有异议，建议转人工客服进一步处理。我也可以先帮你整理订单、商品、售后原因和初步规则判断结果。"


def build_capability_reply() -> str:
    domain = get_active_domain_config()
    return (
        f"我可以作为电商售前与售后智能业务 Agent，当前领域是：{domain.domain_name}。\n"
        "我可以帮你处理：\n"
        "1. 售前咨询，例如“养宠家庭怎么选扫地机器人”。\n"
        "2. 型号详情，例如“RV4001 参数怎么样”。\n"
        "3. 型号对比，例如“对比 RV2001 和 RV4001”。\n"
        "4. 故障排查，例如“扫地机器人不回充怎么办”。\n"
        "5. 订单查询，例如“帮我查 O202605010001”。\n"
        "6. 物流跟踪，例如“物流到哪了”。\n"
        "7. 售后判断和工单生成，例如“这个订单可以退货吗”“我要申请维修”。\n"
        "后续如果切换领域包，也可以迁移到剃须刀、服装、耳机等其他电商品类。"
    )


def build_out_of_scope_reply(category: str) -> str:
    mapping = {"news": "实时新闻或热点资讯", "finance": "投资、股票、彩票或金融预测", "medical": "医疗诊断或治疗建议", "legal": "法律裁判或专业法律意见", "politics": "政治时事或公共事务评论", "general_homework": "与电商业务无关的通用学习写作任务"}
    return f"抱歉，我主要用于电商售后与运营辅助，不能作为通用问答工具处理{mapping.get(category, '当前问题')}。如果你有商品、订单、物流、售后政策、工单或运营数据相关问题，我可以继续帮你处理。"


def check_domain_scope(user_query: str) -> DomainDecision:
    text = user_query.strip()
    if not text:
        return {"allowed": False, "category": "empty", "reason": "用户输入为空", "reply": "请先输入你的问题，例如订单查询、物流查询或售后申请。"}

    if _has_business_signal(text) and not _pure(text, GREETING_WORDS, 20) and not _pure(text, THANKS_WORDS, 30) and not _pure(text, GOODBYE_WORDS, 30):
        return {"allowed": True, "category": "ecommerce_business", "reason": "包含电商业务信号", "reply": None}

    if _contains_any(text, IDENTITY_WORDS):
        return {"allowed": True, "category": "identity", "reason": "询问机器人身份", "reply": build_identity_reply()}
    if _contains_any(text, CAPABILITY_WORDS):
        return {"allowed": True, "category": "capability", "reason": "询问系统能力", "reply": build_capability_reply()}
    if _contains_any(text, HUMAN_SERVICE_WORDS):
        return {"allowed": True, "category": "human_service", "reason": "询问人工客服", "reply": build_human_service_reply()}
    if _pure(text, GREETING_WORDS, 20):
        return {"allowed": True, "category": "small_talk", "reason": "简单问候", "reply": build_greeting_reply()}
    if _pure(text, THANKS_WORDS, 30):
        return {"allowed": True, "category": "small_talk", "reason": "表达感谢", "reply": build_thanks_reply()}
    if _pure(text, GOODBYE_WORDS, 30):
        return {"allowed": True, "category": "small_talk", "reason": "结束对话", "reply": build_goodbye_reply()}

    for group, words in OUT_OF_SCOPE_GROUPS.items():
        if _contains_any(text, words):
            return {"allowed": False, "category": group, "reason": f"非电商业务：{group}", "reply": build_out_of_scope_reply(group)}

    return {"allowed": False, "category": "unknown", "reason": "未识别到电商业务相关意图", "reply": "抱歉，我主要负责电商售后与运营辅助。你可以咨询商品、订单、物流、退换货政策、售后工单或运营数据相关问题。"}
