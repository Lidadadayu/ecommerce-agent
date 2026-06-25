from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    ChatRequest,
    ChatResponse,
    DomainResponse,
    HealthResponse,
    ReviewTaskUpdateRequest,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def include_optional_streaming_routes(app: FastAPI) -> None:
    """
    默认注册 SSE 流式聊天路由，避免启动普通 run_api.py 时 /api/chat/stream 404。
    """

    try:
        from api.stream_routes import router as stream_router

        existing_paths = {getattr(route, "path", "") for route in app.routes}
        if "/api/chat/stream" not in existing_paths:
            app.include_router(stream_router)
    except Exception as exc:
        @app.get("/api/stream/status")
        def stream_status() -> dict[str, Any]:
            return {
                "success": False,
                "message": f"流式路由注册失败：{type(exc).__name__}: {exc}",
            }


def include_optional_upload_routes(app: FastAPI) -> None:
    """
    注册订单截图上传路由。
    """

    try:
        from api.upload_routes import router as upload_router

        existing_paths = {getattr(route, "path", "") for route in app.routes}
        if "/api/uploads/order-screenshot" not in existing_paths:
            app.include_router(upload_router)
    except Exception as exc:
        @app.get("/api/uploads/status")
        def upload_status() -> dict[str, Any]:
            return {
                "success": False,
                "message": f"上传路由注册失败：{type(exc).__name__}: {exc}",
            }


def create_app() -> FastAPI:
    app = FastAPI(
        title="Ecommerce Agent API",
        description="面向电商售前与售后场景的可配置 Agentic RAG 智能业务 Agent API",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", response_model=HealthResponse)
    def root() -> HealthResponse:
        return health()

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        try:
            from agent.domain_loader import get_active_domain_config

            domain = get_active_domain_config()

            return HealthResponse(
                success=True,
                status="ok",
                domain_id=domain.domain_id,
                domain_name=domain.domain_name,
                message="Agent API is running.",
            )
        except Exception as exc:
            return HealthResponse(
                success=False,
                status="error",
                message=f"Agent API started, but domain config failed: {type(exc).__name__}: {exc}",
            )

    @app.get("/api/domain", response_model=DomainResponse)
    def domain_info() -> DomainResponse:
        from agent.domain_loader import get_active_domain_config

        domain = get_active_domain_config()

        return DomainResponse(
            success=True,
            domain_id=domain.domain_id,
            domain_name=domain.domain_name,
            project_title=domain.project_title,
            demo_title=domain.demo_title,
            description=domain.description,
            knowledge_dir=str(domain.knowledge_dir),
            products_file=str(domain.products_file),
            supported_intents=domain.supported_intents,
            knowledge_categories=domain.knowledge_categories,
            prompt_rules=domain.prompt_rules,
        )

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        from agent.agent import run_agent

        start = time.perf_counter()
        session_id = request.session_id or f"S{uuid.uuid4().hex[:12].upper()}"
        customer_id = (request.customer_id or "").strip() or None

        memory = dict(request.memory or {})
        memory.setdefault("session_id", session_id)
        if customer_id:
            memory["user_id"] = customer_id
            memory["customer_id"] = customer_id
            memory["current_customer_id"] = customer_id
        else:
            # 未登录时仍用 session_id 作为演示级 user_id，用于长期记忆隔离。
            memory.setdefault("user_id", session_id)

        try:
            result = run_agent(
                request.user_query,
                memory=memory,
                user_id=memory.get("user_id"),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Agent runtime error: {type(exc).__name__}: {exc}",
            ) from exc

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        if not isinstance(result, dict):
            result = {
                "final_answer": str(result),
                "memory": memory,
                "mode": "non_dict_agent_result",
            }

        result_memory = result.get("memory") if isinstance(result.get("memory"), dict) else memory
        result_memory.setdefault("session_id", session_id)
        result_memory.setdefault("user_id", memory.get("user_id"))
        if customer_id:
            result_memory["customer_id"] = customer_id
            result_memory["current_customer_id"] = customer_id

        return ChatResponse(
            success=True,
            session_id=session_id,
            final_answer=str(result.get("final_answer") or ""),
            memory=result_memory,
            intent=result.get("intent"),
            tool_name=result.get("tool_name"),
            mode=result.get("mode"),
            used_llm=result.get("used_llm"),
            elapsed_ms=result.get("elapsed_ms") or elapsed_ms,
            raw={
                "route": result.get("route"),
                "human_review": result.get("human_review"),
                "human_review_task": result.get("human_review_task"),
                "llm_error": result.get("llm_error"),
                "graph_error": result.get("graph_error"),
                "guard_ok": result.get("guard_ok"),
                "guard_issues": result.get("guard_issues"),
                "context_engineering": result.get("context_engineering"),
                "task_plan": result.get("task_plan"),
                "task_state": (result_memory.get("current_business_context") or {}).get("task_state"),
            },
        )

    @app.get("/api/review-tasks")
    def list_review_tasks(status: str | None = None, limit: int = 50) -> dict[str, Any]:
        from agent.human_review_queue import list_human_review_tasks

        tasks = list_human_review_tasks(status=status, limit=limit)
        return {
            "success": True,
            "count": len(tasks),
            "tasks": tasks,
        }

    @app.get("/api/review-tasks/{review_id}")
    def get_review_task(review_id: str) -> dict[str, Any]:
        from agent.human_review_queue import get_human_review_task

        task = get_human_review_task(review_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Review task not found: {review_id}")

        return {
            "success": True,
            "task": task,
        }

    @app.patch("/api/review-tasks/{review_id}")
    def update_review_task(review_id: str, request: ReviewTaskUpdateRequest) -> dict[str, Any]:
        from agent.human_review_queue import update_human_review_task

        task = update_human_review_task(
            review_id,
            status=request.status,
            reviewer=request.reviewer,
            decision=request.decision,
            comment=request.comment,
        )

        if not task:
            raise HTTPException(status_code=404, detail=f"Review task not found: {review_id}")

        return {
            "success": True,
            "task": task,
        }

    @app.get("/api/logs/recent")
    def recent_logs(limit: int = 20) -> dict[str, Any]:
        from agent.run_logger import load_run_logs, summarize_logs

        records = load_run_logs(limit=limit)
        return {
            "success": True,
            "count": len(records),
            "summary": summarize_logs(records),
            "records": records,
        }

    include_optional_streaming_routes(app)
    include_optional_upload_routes(app)
    return app


app = create_app()
