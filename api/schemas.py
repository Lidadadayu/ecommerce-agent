from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    前端或第三方系统调用 Agent 的请求体。
    """

    user_query: str = Field(..., min_length=1, description="用户输入")
    memory: dict[str, Any] | None = Field(default=None, description="会话记忆，由上一轮响应返回")
    session_id: str | None = Field(default=None, description="前端会话 ID，可选")
    customer_id: str | None = Field(default=None, description="模拟登录用户 ID，例如 C10001")


class ChatResponse(BaseModel):
    """
    Agent 响应体。
    """

    success: bool = True
    session_id: str | None = None
    final_answer: str
    memory: dict[str, Any] = Field(default_factory=dict)
    intent: str | None = None
    tool_name: str | None = None
    mode: str | None = None
    used_llm: bool | None = None
    elapsed_ms: float | None = None
    raw: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    success: bool
    status: str
    domain_id: str | None = None
    domain_name: str | None = None
    message: str


class DomainResponse(BaseModel):
    success: bool
    domain_id: str
    domain_name: str
    project_title: str
    demo_title: str
    description: str
    knowledge_dir: str
    products_file: str
    supported_intents: list[str]
    knowledge_categories: dict[str, str]
    prompt_rules: list[str]


class ReviewTaskUpdateRequest(BaseModel):
    status: str = Field(..., description="pending/approved/rejected/closed")
    reviewer: str | None = None
    decision: str | None = None
    comment: str | None = None
