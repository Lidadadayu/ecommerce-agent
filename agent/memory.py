from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


ORDER_ID_PATTERN = re.compile(r"\bO\d{12}\b")
PRODUCT_ID_PATTERN = re.compile(r"\bP\d{5,}\b")
TICKET_ID_PATTERN = re.compile(r"\bT\d{14}[A-Z0-9]{6}\b")
CUSTOMER_ID_PATTERN = re.compile(r"\bC\d{5,}\b")


def extract_order_id(text: str | None) -> str | None:
    if not text:
        return None
    match = ORDER_ID_PATTERN.search(text)
    return match.group(0) if match else None


def extract_product_id(text: str | None) -> str | None:
    if not text:
        return None
    match = PRODUCT_ID_PATTERN.search(text)
    return match.group(0) if match else None


def extract_ticket_id(text: str | None) -> str | None:
    if not text:
        return None
    match = TICKET_ID_PATTERN.search(text)
    return match.group(0) if match else None


def extract_customer_id(text: str | None) -> str | None:
    if not text:
        return None
    match = CUSTOMER_ID_PATTERN.search(text)
    return match.group(0) if match else None


def is_only_order_id(text: str | None) -> bool:
    if not text:
        return False
    return bool(re.fullmatch(r"\s*O\d{12}\s*", text))


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_text(value: Any, max_len: int = 160) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _deep_find_first(obj: Any, key_names: set[str]) -> Any:
    """
    在嵌套 dict/list 中查找第一个指定 key。
    用于从工具返回结果中提取 order_id / product_id / ticket_id。
    """

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in key_names and value not in (None, ""):
                return value

        for value in obj.values():
            found = _deep_find_first(value, key_names)
            if found not in (None, ""):
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = _deep_find_first(item, key_names)
            if found not in (None, ""):
                return found

    return None


def _deep_find_order(obj: Any) -> dict[str, Any] | None:
    if isinstance(obj, dict):
        if "order_id" in obj and ("order_status" in obj or "items" in obj):
            return obj

        for value in obj.values():
            found = _deep_find_order(value)
            if found:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = _deep_find_order(item)
            if found:
                return found

    return None


def _deep_find_ticket(obj: Any) -> dict[str, Any] | None:
    if isinstance(obj, dict):
        if "ticket_id" in obj and ("ticket_status" in obj or "ticket_type" in obj):
            return obj

        for value in obj.values():
            found = _deep_find_ticket(value)
            if found:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = _deep_find_ticket(item)
            if found:
                return found

    return None


@dataclass
class PendingAction:
    intent: str
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_text)
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "missing_slots": self.missing_slots,
            "created_at": self.created_at,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PendingAction | None":
        if not data:
            return None

        return cls(
            intent=data.get("intent") or "unknown",
            tool_name=data.get("tool_name"),
            arguments=data.get("arguments") or {},
            missing_slots=data.get("missing_slots") or [],
            created_at=data.get("created_at") or _now_text(),
            retry_count=int(data.get("retry_count") or 0),
        )


class SessionMemory:
    """
    会话级短期记忆。

    设计目标：
    1. 记住当前订单、商品、工单。
    2. 记住当前业务流程，例如正在查物流、正在申请退货。
    3. 记录 pending_action，支持缺槽追问。
    4. history 不无限增长，超过阈值后压缩为 conversation_summary。
    5. 对前端友好：可以直接 to_dict / from_dict。
    """

    MAX_RECENT_TURNS = 8
    MAX_SUMMARY_CHARS = 1200

    def __init__(
        self,
        *,
        current_order_id: str | None = None,
        current_customer_id: str | None = None,
        current_product_id: str | None = None,
        current_ticket_id: str | None = None,
        last_intent: str | None = None,
        last_tool_name: str | None = None,
        last_arguments: dict[str, Any] | None = None,
        last_tool_result: dict[str, Any] | None = None,
        pending_action: PendingAction | dict[str, Any] | None = None,
        history: list[dict[str, Any]] | None = None,
        conversation_summary: str = "",
        current_business_context: dict[str, Any] | None = None,
        turn_count: int = 0,
    ) -> None:
        self.current_order_id = current_order_id
        self.current_customer_id = current_customer_id
        self.current_product_id = current_product_id
        self.current_ticket_id = current_ticket_id

        self.last_intent = last_intent
        self.last_tool_name = last_tool_name
        self.last_arguments = last_arguments or {}
        self.last_tool_result = last_tool_result

        if isinstance(pending_action, PendingAction):
            self.pending_action = pending_action
        else:
            self.pending_action = PendingAction.from_dict(pending_action)

        self.history = history or []
        self.conversation_summary = conversation_summary or ""
        self.current_business_context = current_business_context or {}
        self.turn_count = int(turn_count or len(self.history))

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SessionMemory":
        if not data:
            return cls()

        return cls(
            current_order_id=data.get("current_order_id"),
            current_customer_id=data.get("current_customer_id") or data.get("customer_id") or data.get("user_id"),
            current_product_id=data.get("current_product_id"),
            current_ticket_id=data.get("current_ticket_id"),
            last_intent=data.get("last_intent"),
            last_tool_name=data.get("last_tool_name"),
            last_arguments=data.get("last_arguments") or {},
            last_tool_result=data.get("last_tool_result"),
            pending_action=data.get("pending_action"),
            history=data.get("history") or [],
            conversation_summary=data.get("conversation_summary") or "",
            current_business_context=data.get("current_business_context") or {},
            turn_count=int(data.get("turn_count") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_order_id": self.current_order_id,
            "current_customer_id": self.current_customer_id,
            "current_product_id": self.current_product_id,
            "current_ticket_id": self.current_ticket_id,
            "last_intent": self.last_intent,
            "last_tool_name": self.last_tool_name,
            "last_arguments": self.last_arguments,
            "last_tool_result": self.last_tool_result,
            "pending_action": self.pending_action.to_dict() if self.pending_action else None,
            "history": self.history,
            "conversation_summary": self.conversation_summary,
            "current_business_context": self.current_business_context,
            "turn_count": self.turn_count,
        }

    # ------------------------------------------------------------------
    # 基础更新
    # ------------------------------------------------------------------
    def update_from_user_query(self, user_query: str) -> None:
        order_id = extract_order_id(user_query)
        customer_id = extract_customer_id(user_query)
        product_id = extract_product_id(user_query)
        ticket_id = extract_ticket_id(user_query)

        if order_id:
            self.current_order_id = order_id
            self.current_business_context["order_id"] = order_id

        if customer_id:
            self.current_customer_id = customer_id
            self.current_business_context["customer_id"] = customer_id

        if product_id:
            self.current_product_id = product_id
            self.current_business_context["product_id"] = product_id

        if ticket_id:
            self.current_ticket_id = ticket_id
            self.current_business_context["ticket_id"] = ticket_id

        inferred_flow = self._infer_active_flow(user_query)
        if inferred_flow:
            self.current_business_context["active_flow"] = inferred_flow

        ticket_type = self._infer_ticket_type(user_query)
        if ticket_type:
            self.current_business_context["ticket_type"] = ticket_type

    def update_after_tool_call(
        self,
        intent: str | None,
        tool_name: str | None,
        arguments: dict[str, Any] | None,
        tool_result: dict[str, Any] | None,
    ) -> None:
        self.last_intent = intent
        self.last_tool_name = tool_name
        self.last_arguments = arguments or {}
        self.last_tool_result = tool_result

        if intent:
            self.current_business_context["active_flow"] = intent

        for key in ("customer_id", "order_id", "product_id", "ticket_id", "ticket_type", "reason", "package_status"):
            value = (arguments or {}).get(key)
            if value not in (None, ""):
                self.current_business_context[key] = value

        customer_id = (arguments or {}).get("customer_id")
        if customer_id:
            self.current_customer_id = str(customer_id)

        result = tool_result or {}
        found_order_id = _deep_find_first(result, {"order_id", "primary_order_id", "current_order_id"})
        found_customer_id = _deep_find_first(result, {"customer_id"})
        found_product_id = _deep_find_first(result, {"product_id"})
        found_ticket_id = _deep_find_first(result, {"ticket_id"})

        if found_order_id:
            self.current_order_id = str(found_order_id)
            self.current_business_context["order_id"] = str(found_order_id)

            # 截图上传时，前端先保存 evidence_id；订单号通常在 Agent 工具调用后才识别出来。
            # 这里把后识别出的订单号回填到 evidence_files，避免前端右侧仍显示“未识别订单号”。
            evidence_files = self.current_business_context.get("evidence_files")
            if isinstance(evidence_files, list):
                for item in evidence_files:
                    if not isinstance(item, dict):
                        continue
                    item.setdefault("order_id", str(found_order_id))
                    analysis = item.get("screenshot_analysis")
                    if isinstance(analysis, dict):
                        analysis.setdefault("order_id", str(found_order_id))

        if found_customer_id:
            self.current_customer_id = str(found_customer_id)
            self.current_business_context["customer_id"] = str(found_customer_id)

        if found_product_id:
            self.current_product_id = str(found_product_id)
            self.current_business_context["product_id"] = str(found_product_id)

        if found_ticket_id:
            self.current_ticket_id = str(found_ticket_id)
            self.current_business_context["ticket_id"] = str(found_ticket_id)

        order = _deep_find_order(result)
        if order:
            self.current_business_context["order_status"] = order.get("order_status")
            self.current_business_context["payment_amount"] = order.get("payment_amount")
            self.current_business_context["item_count"] = len(order.get("items") or [])

            items = order.get("items") or []
            if len(items) == 1 and items[0].get("product_id"):
                self.current_product_id = items[0]["product_id"]
                self.current_business_context["product_id"] = items[0]["product_id"]
                self.current_business_context["product_name"] = items[0].get("product_name")
            elif len(items) > 1:
                self.current_business_context["candidate_products"] = [
                    {
                        "product_id": item.get("product_id"),
                        "product_name": item.get("product_name"),
                        "category": item.get("category"),
                    }
                    for item in items
                ]

        ticket = _deep_find_ticket(result)
        if ticket:
            self.current_ticket_id = ticket.get("ticket_id") or self.current_ticket_id
            self.current_business_context["ticket_id"] = self.current_ticket_id
            self.current_business_context["ticket_status"] = ticket.get("ticket_status")
            self.current_business_context["ticket_type"] = ticket.get("ticket_type")

    def append_turn(
        self,
        user_query: str,
        assistant_answer: str,
        intent: str | None = None,
        tool_name: str | None = None,
    ) -> None:
        self.turn_count += 1

        self.history.append(
            {
                "turn": self.turn_count,
                "time": _now_text(),
                "user_query": _safe_text(user_query, 240),
                "assistant_answer": _safe_text(assistant_answer, 320),
                "intent": intent,
                "tool_name": tool_name,
            }
        )

        self._compress_history_if_needed()

    # ------------------------------------------------------------------
    # Pending Action
    # ------------------------------------------------------------------
    def set_pending_action(
        self,
        *,
        intent: str,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
        missing_slots: list[str] | None = None,
    ) -> None:
        if self.pending_action and self.pending_action.intent == intent:
            retry_count = self.pending_action.retry_count + 1
        else:
            retry_count = 0

        self.pending_action = PendingAction(
            intent=intent,
            tool_name=tool_name,
            arguments=arguments or {},
            missing_slots=missing_slots or [],
            retry_count=retry_count,
        )

        self.current_business_context["active_flow"] = intent
        self.current_business_context["pending_missing_slots"] = missing_slots or []

        for key, value in (arguments or {}).items():
            if value not in (None, "") and key in {
                "order_id",
                "product_id",
                "ticket_id",
                "ticket_type",
                "reason",
                "package_status",
                "product_name",
            }:
                self.current_business_context[key] = value

    def clear_pending_action(self) -> None:
        self.pending_action = None
        self.current_business_context.pop("pending_missing_slots", None)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def build_memory_summary(self) -> str:
        lines = [
            "【当前会话记忆】",
            f"- 当前订单号：{self.current_order_id or '无'}",
            f"- 当前用户ID：{self.current_customer_id or '无'}",
            f"- 当前商品ID：{self.current_product_id or '无'}",
            f"- 当前工单号：{self.current_ticket_id or '无'}",
        ]

        if self.current_business_context:
            lines.append("- 当前业务上下文：")
            for key, value in self.current_business_context.items():
                if value not in (None, "", [], {}):
                    lines.append(f"  - {key}: {_safe_text(value, 180)}")

        if self.pending_action:
            lines.append("- 当前待补充动作：")
            lines.append(f"  - intent: {self.pending_action.intent}")
            lines.append(f"  - tool_name: {self.pending_action.tool_name}")
            lines.append(f"  - missing_slots: {self.pending_action.missing_slots}")
            lines.append(f"  - known_arguments: {self.pending_action.arguments}")

        if self.conversation_summary:
            lines.append("- 历史摘要：")
            lines.append(_safe_text(self.conversation_summary, 600))

        if self.history:
            lines.append("- 最近对话：")
            for turn in self.history[-4:]:
                lines.append(
                    f"  - 用户：{_safe_text(turn.get('user_query'), 120)}；"
                    f"系统：{_safe_text(turn.get('assistant_answer'), 160)}"
                )

        return "\n".join(lines)

    def _compress_history_if_needed(self) -> None:
        if len(self.history) <= self.MAX_RECENT_TURNS:
            return

        old_turns = self.history[:-self.MAX_RECENT_TURNS]
        self.history = self.history[-self.MAX_RECENT_TURNS:]

        compact_lines = []
        for turn in old_turns:
            compact_lines.append(
                f"[{turn.get('turn')}] 用户问：{_safe_text(turn.get('user_query'), 80)}；"
                f"意图：{turn.get('intent') or '未知'}；工具：{turn.get('tool_name') or '无'}。"
            )

        old_summary = self.conversation_summary.strip()
        new_piece = "\n".join(compact_lines)

        merged = f"{old_summary}\n{new_piece}".strip() if old_summary else new_piece
        if len(merged) > self.MAX_SUMMARY_CHARS:
            merged = merged[-self.MAX_SUMMARY_CHARS:]

        self.conversation_summary = merged

    # ------------------------------------------------------------------
    # Intent helpers
    # ------------------------------------------------------------------
    def _infer_active_flow(self, text: str) -> str | None:
        if any(word in text for word in ["物流", "快递", "到哪", "配送"]):
            return "logistics_query"

        if any(word in text for word in ["退款进度", "退货进度", "钱退", "退款到哪"]):
            return "refund_progress"

        if any(word in text for word in ["工单", "售后单"]):
            return "ticket_query"

        if any(word in text for word in ["我要申请", "帮我申请", "申请退货", "申请换货", "申请维修", "申请退款", "创建工单"]):
            return "ticket_create"

        if any(word in text for word in ["可以退", "可以换", "能不能退", "能不能换", "支持退", "支持换"]):
            return "aftersale_check"

        if any(word in text for word in ["订单", "支付", "发货", "签收"]):
            return "order_query"

        if any(word in text for word in ["商品", "有没有", "搜索", "推荐"]):
            return "product_search"

        return None

    def _infer_ticket_type(self, text: str) -> str | None:
        if "退款" in text or "退钱" in text:
            return "refund"
        if "退货" in text or "退掉" in text:
            return "return"
        if "换货" in text or "更换" in text:
            return "exchange"
        if "维修" in text or "修理" in text or "坏了" in text:
            return "repair"
        if "取消订单" in text:
            return "cancel"
        return None
