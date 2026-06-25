from __future__ import annotations

import html
import os
import re
import time
from typing import Any

import streamlit as st

from frontend_api_client import AgentAPIClient
from frontend_stream_client import AgentStreamClient, AgentStreamError


st.set_page_config(
    page_title="扫地机器人智能客服",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)


DEFAULT_API_BASE_URL = os.getenv("AGENT_API_BASE_URL", "http://127.0.0.1:8001")
DEV_MODE = os.getenv("FRONTEND_DEV_MODE", "0").strip() == "1"


CUSTOMERS = {
    "C10001": {"name": "张三", "label": "C10001 张三", "avatar": "👨"},
    "C10002": {"name": "李四", "label": "C10002 李四", "avatar": "👩"},
    "C10003": {"name": "王五", "label": "C10003 王五", "avatar": "🧑"},
}


EXAMPLE_GROUPS = {
    "售前选购": [
        "我家养猫，预算3000以内，推荐一款扫拖一体机器人",
        "RV4001 参数怎么样",
        "对比 RV2001 和 RV4001",
    ],
    "故障排查": [
        "扫地机器人不回充怎么办？",
        "扫拖一体机器人拖地不出水怎么办？",
        "机器人有烧焦味还能继续用吗？",
    ],
    "订单售后": [
        "我买过哪些商品？",
        "帮我查一下 O202605010001 这个订单",
        "物流到哪了？",
        "这个订单可以维修吗？",
        "我要退 RV4001",
    ],
}


CUSTOM_CSS = """
<style>
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    [data-testid="stDecoration"] {display: none !important;}

    .block-container {
        padding-top: 0.75rem !important;
        padding-bottom: 0.55rem !important;
        max-width: 1420px !important;
    }

    div[data-testid="stVerticalBlock"] { gap: 0.55rem; }

    .app-header {
        padding: 0.85rem 1rem;
        border-radius: 1rem;
        background: linear-gradient(135deg, #fff7ed 0%, #eff6ff 100%);
        border: 1px solid #fed7aa;
        box-shadow: 0 1px 5px rgba(15, 23, 42, 0.06);
        margin-bottom: 0.55rem;
    }

    .app-title {
        font-size: 1.45rem;
        font-weight: 850;
        color: #1f2937;
        margin-bottom: 0.16rem;
        line-height: 1.25;
    }

    .app-subtitle {
        font-size: 0.91rem;
        color: #6b7280;
        line-height: 1.38;
    }

    .card-title {
        font-weight: 780;
        color: #374151;
        font-size: 0.98rem;
        margin-bottom: 0.45rem;
    }

    .mini-text {
        color: #6b7280;
        font-size: 0.82rem;
        line-height: 1.45;
    }

    .status-ok {
        background: #ecfdf5;
        color: #065f46;
        border: 1px solid #a7f3d0;
        padding: 0.46rem 0.6rem;
        border-radius: 0.68rem;
        font-size: 0.84rem;
        margin-bottom: 0.45rem;
    }

    .status-bad {
        background: #fef2f2;
        color: #991b1b;
        border: 1px solid #fecaca;
        padding: 0.46rem 0.6rem;
        border-radius: 0.68rem;
        font-size: 0.84rem;
        margin-bottom: 0.45rem;
    }

    .user-card {
        border: 1px solid #fed7aa;
        background: #fff7ed;
        border-radius: 0.85rem;
        padding: 0.65rem 0.7rem;
        margin-bottom: 0.5rem;
    }

    .user-name {
        font-weight: 800;
        color: #1f2937;
        font-size: 0.95rem;
    }

    .user-desc {
        color: #6b7280;
        font-size: 0.78rem;
        margin-top: 0.1rem;
    }

    .service-pill {
        display: inline-block;
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 999px;
        padding: 0.25rem 0.55rem;
        margin: 0.15rem 0.1rem 0.15rem 0;
        font-size: 0.78rem;
        color: #4b5563;
    }

    .empty-chat {
        min-height: 420px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px dashed #d1d5db;
        border-radius: 0.95rem;
        background: #fafafa;
        color: #6b7280;
        font-size: 0.94rem;
        text-align: center;
        padding: 2rem;
    }

    .task-card {
        border: 1px solid #e5e7eb;
        background: #ffffff;
        border-radius: 0.9rem;
        padding: 0.7rem 0.75rem;
        margin-bottom: 0.5rem;
    }

    .task-title {
        font-weight: 780;
        color: #1f2937;
        font-size: 0.9rem;
    }

    .task-msg {
        color: #6b7280;
        font-size: 0.82rem;
        margin-top: 0.15rem;
        line-height: 1.45;
    }

    .progress-wrap {
        width: 100%;
        height: 0.42rem;
        background: #f3f4f6;
        border-radius: 999px;
        overflow: hidden;
        margin-top: 0.5rem;
    }

    .progress-bar {
        height: 100%;
        background: linear-gradient(90deg, #fb923c, #f97316);
        border-radius: 999px;
        transition: width 0.2s ease;
    }

    .typing-dots {
        display: inline-flex;
        align-items: center;
        gap: 0.22rem;
        margin-left: 0.35rem;
    }

    .typing-dots span {
        width: 0.36rem;
        height: 0.36rem;
        background: #f97316;
        border-radius: 999px;
        display: inline-block;
        animation: bounce 1.2s infinite ease-in-out;
    }

    .typing-dots span:nth-child(2) { animation-delay: 0.15s; }
    .typing-dots span:nth-child(3) { animation-delay: 0.30s; }

    @keyframes bounce {
        0%, 80%, 100% { transform: translateY(0); opacity: 0.45; }
        40% { transform: translateY(-5px); opacity: 1; }
    }

    .small-divider {
        height: 1px;
        background: #e5e7eb;
        margin: 0.58rem 0;
    }

    .stButton > button {
        border-radius: 0.72rem !important;
        height: auto !important;
        min-height: 2.22rem !important;
        padding: 0.35rem 0.58rem !important;
        font-size: 0.86rem !important;
        background: #ffffff;
        border: 1px solid #e5e7eb;
    }

    .stButton > button:hover {
        border-color: #f97316;
        color: #c2410c;
        background: #fff7ed;
    }


    .chat-composer {
        border: 1px solid #fed7aa;
        background: #fffaf5;
        border-radius: 1rem;
        padding: 0.7rem 0.75rem 0.45rem 0.75rem;
        margin-top: 0.55rem;
    }

    .composer-caption {
        color: #92400e;
        font-size: 0.78rem;
        line-height: 1.35;
        margin-bottom: 0.2rem;
    }

    .attachment-chip {
        display: inline-block;
        border: 1px solid #fdba74;
        background: #fffbeb;
        color: #92400e;
        border-radius: 999px;
        padding: 0.18rem 0.48rem;
        font-size: 0.76rem;
        margin: 0.1rem 0.12rem 0.1rem 0;
    }

    .attachment-link {
        display: inline-block;
        text-decoration: none !important;
        border: 1px solid #fdba74;
        background: #fff7ed;
        color: #c2410c !important;
        border-radius: 999px;
        padding: 0.18rem 0.52rem;
        font-size: 0.76rem;
        margin: 0.1rem 0 0.15rem 0.1rem;
    }

    .attachment-link:hover {
        border-color: #f97316;
        background: #ffedd5;
        color: #9a3412 !important;
    }

    .spinner-ring {
        display: inline-block;
        width: 0.9rem;
        height: 0.9rem;
        border: 2px solid #fed7aa;
        border-top-color: #f97316;
        border-radius: 50%;
        margin-left: 0.42rem;
        vertical-align: -0.12rem;
        animation: spin 0.82s linear infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    .thinking-bubble {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        color: #92400e;
        background: #fff7ed;
        border: 1px solid #fed7aa;
        border-radius: 999px;
        padding: 0.42rem 0.72rem;
        font-size: 0.88rem;
        font-weight: 650;
        line-height: 1.2;
    }

</style>
"""


def init_state() -> None:
    defaults = {
        "api_base_url": DEFAULT_API_BASE_URL,
        "api_health": None,
        "api_domain": None,
        "selected_customer_id": "C10001",
        "customer_sessions": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def normal_client() -> AgentAPIClient:
    return AgentAPIClient(st.session_state.api_base_url)


def stream_client() -> AgentStreamClient:
    return AgentStreamClient(st.session_state.api_base_url)


def safe_api_call(func, fallback: Any = None) -> Any:
    try:
        return func()
    except Exception:
        return fallback


def refresh_api_status() -> None:
    c = normal_client()
    st.session_state.api_health = safe_api_call(c.health, {"success": False, "message": "API 未连接"})
    st.session_state.api_domain = safe_api_call(c.domain, None)


def current_customer_id() -> str:
    cid = st.session_state.get("selected_customer_id") or "C10001"
    return cid if cid in CUSTOMERS else "C10001"


def current_customer() -> dict[str, str]:
    return CUSTOMERS[current_customer_id()]


def get_user_session(customer_id: str | None = None) -> dict[str, Any]:
    cid = customer_id or current_customer_id()
    sessions = st.session_state.customer_sessions

    if cid not in sessions:
        sessions[cid] = {
            "messages": [],
            "memory": {"customer_id": cid, "user_id": cid},
            "session_id": None,
            "last_meta": None,
            "task_status": None,
            "pending_query": None,
        }

    session = sessions[cid]
    session.setdefault("messages", [])
    session.setdefault("memory", {"customer_id": cid, "user_id": cid})
    session.setdefault("session_id", None)
    session.setdefault("last_meta", None)
    session.setdefault("task_status", None)
    session.setdefault("pending_query", None)

    memory = dict(session.get("memory") or {})
    memory.setdefault("customer_id", cid)
    memory.setdefault("user_id", cid)
    session["memory"] = memory
    return session


def clear_current_chat() -> None:
    cid = current_customer_id()
    st.session_state.customer_sessions[cid] = {
        "messages": [],
        "memory": {"customer_id": cid, "user_id": cid},
        "session_id": None,
        "last_meta": None,
        "task_status": None,
        "pending_query": None,
    }


def _dedupe_keep_order(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in unique:
            unique.append(item)
    return unique


ORDER_ID_RE = re.compile(r"\bO\d{12}\b")


def _find_order_id_in_obj(obj: Any) -> str:
    """从前端会话 memory / 工具结果 / 截图分析中递归寻找订单号。"""

    if obj is None:
        return ""

    if isinstance(obj, str):
        match = ORDER_ID_RE.search(obj)
        return match.group(0) if match else ""

    if isinstance(obj, dict):
        for key in ("order_id", "primary_order_id", "current_order_id"):
            value = obj.get(key)
            found = _find_order_id_in_obj(value)
            if found:
                return found
        for value in obj.values():
            found = _find_order_id_in_obj(value)
            if found:
                return found

    if isinstance(obj, list):
        for item in obj:
            found = _find_order_id_in_obj(item)
            if found:
                return found

    return ""


def _current_order_id_from_memory(memory: dict[str, Any] | None = None) -> str:
    if memory is None:
        session = get_user_session()
        memory = session.get("memory") if isinstance(session.get("memory"), dict) else {}

    context = memory.get("current_business_context") if isinstance(memory.get("current_business_context"), dict) else {}
    candidates = [
        memory.get("current_order_id"),
        context.get("order_id"),
        context.get("last_screenshot_analysis"),
        memory.get("last_tool_result"),
        context.get("evidence_files"),
    ]
    for item in candidates:
        found = _find_order_id_in_obj(item)
        if found:
            return found
    return ""


def sync_evidence_order_ids(session: dict[str, Any] | None = None) -> None:
    """把 Agent 后续识别出的订单号同步回截图 chip 和右侧“当前截图”区域。"""

    session = session or get_user_session()
    memory = session.get("memory") if isinstance(session.get("memory"), dict) else {}
    if not memory:
        return

    order_id = _current_order_id_from_memory(memory)
    if not order_id:
        return

    context = memory.get("current_business_context") if isinstance(memory.get("current_business_context"), dict) else {}
    evidence_files = context.get("evidence_files") if isinstance(context.get("evidence_files"), list) else []

    evidence_order_map: dict[str, str] = {}
    changed = False
    for item in evidence_files:
        if not isinstance(item, dict):
            continue
        eid = str(item.get("evidence_id") or "")
        item_order = _find_order_id_in_obj(item.get("order_id")) or _find_order_id_in_obj(item.get("screenshot_analysis")) or order_id
        if item_order:
            evidence_order_map[eid] = item_order
        if item_order and not item.get("order_id"):
            item["order_id"] = item_order
            changed = True
        analysis = item.get("screenshot_analysis")
        if isinstance(analysis, dict) and item_order and not analysis.get("order_id"):
            analysis["order_id"] = item_order
            changed = True

    for message in session.get("messages") or []:
        attachments = message.get("attachments") if isinstance(message.get("attachments"), list) else []
        for item in attachments:
            if not isinstance(item, dict) or item.get("order_id"):
                continue
            eid = str(item.get("evidence_id") or "")
            item_order = evidence_order_map.get(eid) or order_id
            if item_order:
                item["order_id"] = item_order
                changed = True

    if changed:
        context["evidence_files"] = evidence_files
        context.setdefault("order_id", order_id)
        memory.setdefault("current_order_id", order_id)
        memory["current_business_context"] = context
        session["memory"] = memory


def attach_evidence_to_session(evidence: dict[str, Any]) -> None:
    """
    将上传凭证写入当前前端会话记忆。

    LangGraph 工具调用节点会从 memory.current_business_context 中读取 evidence_ids，
    因此这里是“上传截图 -> 创建售后工单自动携带凭证”的关键连接点。
    """

    evidence_id = str(evidence.get("evidence_id") or "").strip()
    if not evidence_id:
        return

    session = get_user_session()
    cid = current_customer_id()

    memory = dict(session.get("memory") or {})
    memory.setdefault("customer_id", cid)
    memory.setdefault("user_id", cid)
    memory.setdefault("current_customer_id", cid)

    context = dict(memory.get("current_business_context") or {})

    evidence_ids = context.get("evidence_ids") if isinstance(context.get("evidence_ids"), list) else []
    context["evidence_ids"] = _dedupe_keep_order([*evidence_ids, evidence_id])[:10]

    evidence_files = context.get("evidence_files") if isinstance(context.get("evidence_files"), list) else []
    compact = {
        "evidence_id": evidence_id,
        "original_filename": evidence.get("original_filename"),
        "file_url": evidence.get("file_url"),
        "order_id": evidence.get("order_id"),
        "created_at": evidence.get("created_at"),
        "note": evidence.get("note"),
        "screenshot_analysis": evidence.get("screenshot_analysis"),
    }
    evidence_files = [item for item in evidence_files if not (isinstance(item, dict) and item.get("evidence_id") == evidence_id)]
    evidence_files.insert(0, compact)
    context["evidence_files"] = evidence_files[:10]

    analysis = evidence.get("screenshot_analysis") if isinstance(evidence.get("screenshot_analysis"), dict) else {}
    context["last_screenshot_analysis"] = analysis or context.get("last_screenshot_analysis")

    order_id = str(evidence.get("order_id") or analysis.get("order_id") or "").strip()
    if order_id:
        context["order_id"] = order_id
        memory["current_order_id"] = order_id

    product_names = analysis.get("product_names") if isinstance(analysis.get("product_names"), list) else []
    if product_names:
        context["screenshot_product_names"] = product_names[:5]

    context["active_flow"] = "screenshot_order_review"
    memory["current_business_context"] = context
    session["memory"] = memory


def _current_evidence_files() -> list[dict[str, Any]]:
    session = get_user_session()
    memory = session.get("memory") if isinstance(session.get("memory"), dict) else {}
    context = memory.get("current_business_context") if isinstance(memory.get("current_business_context"), dict) else {}
    files = context.get("evidence_files") if isinstance(context.get("evidence_files"), list) else []
    return [item for item in files if isinstance(item, dict)]


def render_upload_panel() -> None:
    session = get_user_session()
    memory = session.get("memory") if isinstance(session.get("memory"), dict) else {}
    context = memory.get("current_business_context") if isinstance(memory.get("current_business_context"), dict) else {}

    cid = current_customer_id()
    session_id = session.get("session_id")
    current_order = str(
        context.get("order_id")
        or memory.get("current_order_id")
        or ""
    )

    st.markdown('<div class="small-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📎 订单截图凭证</div>', unsafe_allow_html=True)
    st.caption("上传后会自动关联当前会话；后续创建售后工单时，系统会自动携带 evidence_id 供人工客服审核。")

    uploaded_file = st.file_uploader(
        "上传订单截图",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=False,
        key=f"order_screenshot_upload_{cid}",
        label_visibility="collapsed",
    )

    order_id = st.text_input(
        "关联订单号（可选）",
        value=current_order,
        placeholder="例如 O202605010001",
        key=f"upload_order_id_{cid}",
    ).strip()
    note = st.text_input(
        "备注（可选）",
        value="",
        placeholder="例如：退货申请凭证、订单截图",
        key=f"upload_note_{cid}",
    ).strip()

    if st.button("上传并关联", use_container_width=True, key=f"upload_btn_{cid}"):
        if uploaded_file is None:
            st.warning("请先选择一张订单截图。")
        else:
            try:
                result = normal_client().upload_order_screenshot(
                    file_obj=uploaded_file,
                    customer_id=cid,
                    session_id=session_id,
                    order_id=order_id or None,
                    note=note or None,
                )
                evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
                attach_evidence_to_session(evidence)
                st.success(f"上传成功，凭证 ID：{evidence.get('evidence_id')}")
                st.rerun()
            except Exception as exc:
                st.error(f"上传失败：{exc}")

    evidence_files = _current_evidence_files()
    if evidence_files:
        with st.expander(f"当前会话已关联 {len(evidence_files)} 个凭证", expanded=True):
            for item in evidence_files[:5]:
                eid = str(item.get("evidence_id") or "")
                name = html.escape(str(item.get("original_filename") or "订单截图"))
                linked_order = html.escape(str(item.get("order_id") or "未填写"))
                created_at = html.escape(str(item.get("created_at") or ""))
                st.markdown(f"**{eid}** · {name}")
                st.caption(f"订单号：{linked_order} · 上传时间：{created_at}")
                if eid:
                    st.link_button("查看文件", normal_client().evidence_file_url(eid), use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("刷新用户凭证", use_container_width=True, key=f"refresh_evidences_{cid}"):
            try:
                listed = normal_client().list_evidences(customer_id=cid, limit=10)
                evidences = listed.get("evidences") if isinstance(listed.get("evidences"), list) else []
                for evidence in evidences:
                    if isinstance(evidence, dict):
                        attach_evidence_to_session(evidence)
                st.success(f"已同步 {len(evidences)} 个最近凭证。")
                st.rerun()
            except Exception as exc:
                st.error(f"刷新失败：{exc}")
    with col_b:
        if st.button("清空关联", use_container_width=True, key=f"clear_evidences_{cid}"):
            memory = dict(session.get("memory") or {})
            context = dict(memory.get("current_business_context") or {})
            context.pop("evidence_ids", None)
            context.pop("evidence_files", None)
            memory["current_business_context"] = context
            session["memory"] = memory
            st.rerun()


def task_html(title: str, message: str, progress: float = 0.0, *, animated: bool = True) -> str:
    pct = max(0, min(100, int(progress * 100)))
    spinner = '<span class="spinner-ring"></span>' if animated else ""
    return f"""
    <div class="task-card">
        <div class="task-title">{html.escape(title)}{spinner}</div>
        <div class="task-msg">{html.escape(message)}</div>
        <div class="progress-wrap"><div class="progress-bar" style="width:{pct}%"></div></div>
    </div>
    """


def thinking_html() -> str:
    return """
    <div class="thinking-bubble">
        <span>正在思考</span>
        <span class="spinner-ring"></span>
    </div>
    """


def render_thinking_placeholder(placeholder: Any) -> None:
    placeholder.markdown(thinking_html(), unsafe_allow_html=True)


def start_query(query: str, *, attachments: list[dict[str, Any]] | None = None, display_content: str | None = None) -> None:
    query = (query or "").strip()
    attachments = attachments or []
    if not query and not attachments:
        return

    if not query and attachments:
        query = "我上传了一张订单截图，请帮我识别截图中的订单信息，并告诉我接下来可以对这个订单做什么操作。"

    session = get_user_session()
    content = (display_content or query).strip()
    session["messages"].append({"role": "user", "content": content, "attachments": attachments})
    session["pending_query"] = query
    session["task_status"] = {"title": "处理中", "message": "正在处理。", "progress": 0.02}


def submit_example(query: str) -> None:
    start_query(query)
    st.rerun()


def call_stream_for_pending_query(chat_box: Any) -> None:
    session = get_user_session()
    pending_query = session.get("pending_query")
    if not pending_query:
        return

    cid = current_customer_id()
    customer = current_customer()

    with chat_box:
        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            answer_placeholder = st.empty()
            full_answer = ""
            render_thinking_placeholder(status_placeholder)

            try:
                for event in stream_client().stream_chat(
                    pending_query,
                    memory=session.get("memory"),
                    session_id=session.get("session_id"),
                    customer_id=cid,
                ):
                    event_type = event.get("event")

                    if event_type in {"connected", "status", "route", "tool_start"}:
                        status_event = {
                            "title": event.get("title") or {
                                "connected": "连接成功",
                                "route": "识别完成",
                                "tool_start": "查询业务信息",
                            }.get(event_type, "处理中"),
                            "message": event.get("message") or "正在处理。",
                            "progress": event.get("progress") or 0.1,
                            "stage": event.get("stage") or event_type,
                        }
                        session["task_status"] = status_event
                        render_thinking_placeholder(status_placeholder)

                    elif event_type == "answer_delta":
                        full_answer += str(event.get("content") or "")
                        answer_placeholder.markdown(full_answer)

                    elif event_type == "final":
                        status_event = event.get("task_status") or {
                            "title": "处理完成",
                            "message": "已完成本次客服处理。",
                            "progress": 1.0,
                            "stage": "done",
                        }
                        session["task_status"] = status_event
                        status_placeholder.empty()

                        final_answer = str(event.get("final_answer") or full_answer or "系统没有返回回答。")
                        answer_placeholder.markdown(final_answer)

                        memory = event.get("memory") or {}
                        if isinstance(memory, dict):
                            memory.setdefault("customer_id", cid)
                            memory.setdefault("user_id", cid)
                        session["memory"] = memory
                        sync_evidence_order_ids(session)
                        session["session_id"] = event.get("session_id") or session.get("session_id")
                        session["last_meta"] = {
                            "session_id": event.get("session_id"),
                            "intent": event.get("intent"),
                            "tool_name": event.get("tool_name"),
                            "mode": event.get("mode"),
                            "elapsed_ms": event.get("elapsed_ms"),
                            "guard_ok": event.get("guard_ok"),
                            "customer_id": cid,
                            "customer_name": customer.get("name"),
                        }
                        full_answer = final_answer

                    elif event_type == "error":
                        error_text = str(event.get("message") or "流式处理失败。")
                        status_placeholder.error(error_text)
                        full_answer = error_text

                    elif event_type == "done":
                        pass

                if full_answer:
                    session["messages"].append({"role": "assistant", "content": full_answer})
                else:
                    fallback = "系统没有返回回答。"
                    session["messages"].append({"role": "assistant", "content": fallback})
                    answer_placeholder.warning(fallback)

                session["pending_query"] = None

            except AgentStreamError as exc:
                answer = f"我暂时无法连接流式后端，请检查 API 是否已启动。\n\n错误信息：{exc}"
                status_placeholder.error("流式连接失败")
                answer_placeholder.warning(answer)
                session["messages"].append({"role": "assistant", "content": answer})
                session["pending_query"] = None

            except Exception as exc:
                answer = f"系统处理时遇到异常：{type(exc).__name__}: {exc}"
                status_placeholder.error("系统异常")
                answer_placeholder.error(answer)
                session["messages"].append({"role": "assistant", "content": answer})
                session["pending_query"] = None

    time.sleep(0.12)
    st.rerun()


def render_header() -> None:
    domain = st.session_state.get("api_domain") or {}
    domain_name = domain.get("domain_name") or "扫地机器人与扫拖一体机器人"

    st.markdown(
        f"""
        <div class="app-header">
            <div class="app-title">🤖 一体化智能客服</div>
            <div class="app-subtitle">
                当前领域：{html.escape(str(domain_name))} · 支持选购推荐、故障排查、订单物流与售后服务 · 已启用后端流式状态
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_left_panel() -> None:
    st.markdown('<div class="card-title">👤 模拟登录</div>', unsafe_allow_html=True)

    customer_ids = list(CUSTOMERS.keys())
    old_cid = current_customer_id()
    selected_label = st.selectbox(
        "选择当前用户",
        options=[CUSTOMERS[cid]["label"] for cid in customer_ids],
        index=customer_ids.index(old_cid),
        label_visibility="collapsed",
    )
    selected_cid = selected_label.split(" ", 1)[0]
    if selected_cid != old_cid:
        st.session_state.selected_customer_id = selected_cid
        get_user_session(selected_cid)
        st.rerun()

    customer = current_customer()
    st.markdown(
        f"""
        <div class="user-card">
            <div class="user-name">{customer.get("avatar")} {html.escape(customer["label"])}</div>
            <div class="user-desc">当前对话、记忆和订单权限均按用户隔离。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="card-title">🧭 常用入口</div>', unsafe_allow_html=True)

    for group_name, queries in EXAMPLE_GROUPS.items():
        with st.expander(group_name, expanded=(group_name == "售前选购")):
            for q in queries:
                if st.button(q, key=f"example_{group_name}_{q}", use_container_width=True):
                    submit_example(q)

    st.markdown('<div class="small-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="card-title">⚙️ 服务连接</div>', unsafe_allow_html=True)

    raw_api_url = st.text_input(
        "后端 API 地址",
        value=str(st.session_state.get("api_base_url") or DEFAULT_API_BASE_URL),
        label_visibility="collapsed",
    )
    st.session_state.api_base_url = (raw_api_url or DEFAULT_API_BASE_URL).strip().rstrip("/")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("检查连接", use_container_width=True):
            refresh_api_status()
            st.rerun()
    with col2:
        if st.button("清空对话", use_container_width=True):
            clear_current_chat()
            st.rerun()

    health = st.session_state.get("api_health")
    if health and health.get("success"):
        st.markdown("<div class='status-ok'>服务已连接</div>", unsafe_allow_html=True)
    elif health:
        st.markdown("<div class='status-bad'>服务未连接</div>", unsafe_allow_html=True)



def _render_message_attachments(message: dict[str, Any]) -> None:
    attachments = message.get("attachments") if isinstance(message.get("attachments"), list) else []
    if not attachments:
        return

    for idx, item in enumerate(attachments[:5]):
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("evidence_id") or "")
        filename = html.escape(str(item.get("original_filename") or "订单截图"))
        order_text = item.get("order_id") or _current_order_id_from_memory() or "未识别订单号"
        order_id = html.escape(str(order_text))
        st.markdown(
            f'<span class="attachment-chip">📎 {filename} · {order_id}</span>',
            unsafe_allow_html=True,
        )
        file_url = item.get("absolute_file_url") or (normal_client().evidence_file_url(evidence_id) if evidence_id else "")
        if file_url:
            # st.link_button 在部分 Streamlit 版本中不支持 key 参数。
            # 这里使用普通 HTML 链接渲染附件，避免同名按钮或版本差异导致页面崩溃。
            safe_url = html.escape(str(file_url), quote=True)
            st.markdown(
                f'<a class="attachment-link" href="{safe_url}" target="_blank" rel="noopener noreferrer">查看截图</a>',
                unsafe_allow_html=True,
            )


def _upload_chat_attachments(uploaded_files: list[Any], query: str) -> list[dict[str, Any]]:
    cid = current_customer_id()
    session = get_user_session()
    attachments: list[dict[str, Any]] = []

    for uploaded_file in uploaded_files[:3]:
        result = normal_client().upload_order_screenshot(
            file_obj=uploaded_file,
            customer_id=cid,
            session_id=session.get("session_id"),
            note=(query or "聊天区上传订单截图")[:300],
        )
        evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
        attach_evidence_to_session(evidence)

        evidence_id = str(evidence.get("evidence_id") or "")
        compact = {
            "evidence_id": evidence_id,
            "original_filename": evidence.get("original_filename") or getattr(uploaded_file, "name", "订单截图"),
            "order_id": evidence.get("order_id") or (evidence.get("screenshot_analysis") or {}).get("order_id"),
            "file_url": evidence.get("file_url"),
            "absolute_file_url": normal_client().evidence_file_url(evidence_id) if evidence_id else None,
        }
        attachments.append(compact)

    return attachments


def render_chat_composer() -> None:
    st.markdown('<div class="chat-composer">', unsafe_allow_html=True)
    st.markdown(
        '<div class="composer-caption">可直接输入问题，也可以同时上传订单截图；只上传截图也会自动触发订单信息识别。</div>',
        unsafe_allow_html=True,
    )

    # 不再使用 st.form 包裹 file_uploader。
    # 部分 Streamlit 版本在 form + file_uploader + clear_on_submit=True 组合下，
    # 点击提交后状态不稳定；同时上传接口如果同步等待视觉模型，会让用户感觉“发送没反应”。
    # 这里改成普通组件 + 动态 key：点击发送后先快速上传截图，再进入 Agent 流式处理。
    cid = current_customer_id()
    composer_version = int(st.session_state.get(f"chat_composer_version_{cid}", 0))
    widget_suffix = f"{cid}_{composer_version}"

    uploaded_files = st.file_uploader(
        "订单截图（可选）",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"chat_upload_{widget_suffix}",
        help="支持订单详情页、物流页或售后页截图，最多处理前 3 张。",
    )
    user_query = st.text_area(
        "输入问题",
        placeholder="例如：帮我看下这个订单可以做什么；或者：我要申请退货，原因是不想要了，未拆封",
        height=74,
        key=f"chat_query_{widget_suffix}",
    )
    submitted = st.button("发送", use_container_width=True, key=f"chat_send_{widget_suffix}")

    st.markdown('</div>', unsafe_allow_html=True)

    if not submitted:
        return

    query = (user_query or "").strip()
    files = list(uploaded_files or [])

    if not query and not files:
        st.warning("请输入问题，或上传一张订单截图。")
        return

    attachments: list[dict[str, Any]] = []
    if files:
        with st.spinner("正在上传订单截图，上传完成后会进入 Agent 识别流程……"):
            try:
                attachments = _upload_chat_attachments(files, query)
            except Exception as exc:
                st.error(f"截图上传失败：{exc}")
                return

    if attachments and not query:
        query_to_send = "我上传了一张订单截图，请帮我识别截图中的订单信息，并告诉我接下来可以对这个订单做什么操作。"
    elif attachments and any(word in query for word in ["识别", "看看", "看下", "这个订单", "订单截图", "截图"]):
        query_to_send = f"我上传了一张订单截图。{query}"
    else:
        query_to_send = query

    display_lines: list[str] = []
    if query:
        display_lines.append(query)
    if attachments:
        names = "、".join(str(item.get("original_filename") or "订单截图") for item in attachments)
        display_lines.append(f"已上传订单截图：{names}")

    start_query(query_to_send, attachments=attachments, display_content="\n".join(display_lines))

    # 改变组件 key，下一轮渲染时自动清空上传控件和文本框。
    st.session_state[f"chat_composer_version_{cid}"] = composer_version + 1
    st.rerun()

def render_chat_panel() -> None:
    st.markdown('<div class="card-title">💬 客服对话</div>', unsafe_allow_html=True)

    session = get_user_session()
    sync_evidence_order_ids(session)
    messages = session.get("messages") or []

    chat_box = st.container(height=585, border=True)

    with chat_box:
        if not messages:
            st.markdown(
                """
                <div class="empty-chat">
                    <div>
                        <b>请输入问题开始对话</b><br/>
                        例如：3000以内推荐一款扫拖一体机器人<br/>
                        或：上传订单截图，让我识别订单信息并继续处理售后/物流
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            for message in messages:
                with st.chat_message(message.get("role", "assistant")):
                    st.markdown(str(message.get("content") or ""))
                    _render_message_attachments(message)

    call_stream_for_pending_query(chat_box)

    render_chat_composer()


def render_right_panel() -> None:
    session = get_user_session()
    sync_evidence_order_ids(session)
    task = session.get("task_status") or {}
    meta = session.get("last_meta") or {}
    customer = current_customer()

    st.markdown('<div class="card-title">📍 当前任务状态</div>', unsafe_allow_html=True)
    if task:
        st.markdown(
            task_html(
                str(task.get("title") or "空闲"),
                str(task.get("message") or "当前没有正在处理的任务。"),
                float(task.get("progress") or 0),
                animated=task.get("stage") != "done",
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            task_html("空闲", "当前没有正在处理的任务。", 0.0, animated=False),
            unsafe_allow_html=True,
        )

    evidence_files = _current_evidence_files()
    if evidence_files:
        st.markdown('<div class="small-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📎 当前截图</div>', unsafe_allow_html=True)
        for item in evidence_files[:3]:
            eid = html.escape(str(item.get("evidence_id") or ""))
            memory_for_order = session.get("memory") if isinstance(session.get("memory"), dict) else {}
            order_text = item.get("order_id") or _current_order_id_from_memory(memory_for_order) or "未识别订单号"
            order_id = html.escape(str(order_text))
            st.markdown(f'<span class="service-pill">{eid} · {order_id}</span>', unsafe_allow_html=True)

    st.markdown('<div class="small-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🟢 服务信息</div>', unsafe_allow_html=True)

    health = st.session_state.get("api_health") or {}
    service_text = "正常" if health.get("success") else "未确认"
    st.markdown(f'<span class="service-pill">服务：{service_text}</span>', unsafe_allow_html=True)
    st.markdown(f'<span class="service-pill">用户：{html.escape(customer["name"])}</span>', unsafe_allow_html=True)
    st.markdown(f'<span class="service-pill">对话：{len(session.get("messages") or [])}</span>', unsafe_allow_html=True)

    if meta:
        st.markdown(f'<span class="service-pill">最近响应：{html.escape(str(meta.get("elapsed_ms") or "-"))} ms</span>', unsafe_allow_html=True)
        st.markdown(f'<span class="service-pill">安全检查：{"通过" if meta.get("guard_ok") is not False else "已修正"}</span>', unsafe_allow_html=True)

    st.markdown('<div class="small-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📌 可办理业务</div>', unsafe_allow_html=True)
    for item in ["商品推荐", "购买记录", "故障排查", "订单物流", "售后申请", "人工审核"]:
        st.markdown(f'<span class="service-pill">{html.escape(item)}</span>', unsafe_allow_html=True)

    if DEV_MODE:
        st.markdown('<div class="small-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🛠 开发调试</div>', unsafe_allow_html=True)
        with st.expander("查看调试信息", expanded=False):
            st.write("last_meta")
            st.json(meta)
            st.write("memory")
            st.json(session.get("memory") or {})
            st.write("session_id")
            st.code(str(session.get("session_id")))


def main() -> None:
    init_state()
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    if st.session_state.api_health is None:
        refresh_api_status()

    render_header()

    left, center, right = st.columns([0.24, 0.54, 0.22], gap="medium")

    with left:
        render_left_panel()

    with center:
        render_chat_panel()

    with right:
        render_right_panel()


if __name__ == "__main__":
    main()
