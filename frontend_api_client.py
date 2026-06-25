from __future__ import annotations

import os
from pathlib import Path
from typing import Any, BinaryIO

import requests


DEFAULT_API_BASE_URL = os.getenv("AGENT_API_BASE_URL", "http://127.0.0.1:8001")


class AgentAPIError(RuntimeError):
    pass


class AgentAPIClient:
    """
    Streamlit 前端调用 FastAPI 后端的轻量客户端。

    已覆盖：
    - 健康检查 / 领域信息；
    - 普通聊天；
    - 最近运行日志；
    - 人工审核任务；
    - 订单截图凭证上传与查询。
    """

    def __init__(self, base_url: str | None = None, timeout: int = 120) -> None:
        self.base_url = (base_url or DEFAULT_API_BASE_URL).rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        try:
            response = requests.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
                data=data,
                files=files,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise AgentAPIError(f"无法连接 Agent API：{exc}") from exc

        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise AgentAPIError(f"Agent API 返回错误 {response.status_code}: {detail}")

        try:
            payload = response.json()
        except Exception as exc:
            raise AgentAPIError(f"Agent API 返回内容不是 JSON：{response.text[:300]}") from exc

        if not isinstance(payload, dict):
            raise AgentAPIError("Agent API 返回格式异常：不是 JSON object")

        return payload

    # ------------------------------------------------------------------
    # 基础接口
    # ------------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/health")

    def domain(self) -> dict[str, Any]:
        return self._request("GET", "/api/domain")

    def chat(
        self,
        user_query: str,
        *,
        memory: dict[str, Any] | None = None,
        session_id: str | None = None,
        customer_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "user_query": user_query,
            "memory": memory or {},
            "session_id": session_id,
        }

        # 兼容后端新增 customer_id 的版本。
        # 如果后端 schema 暂未使用 customer_id，通常 Pydantic 会忽略额外字段；
        # 如果后端已支持，则可用于订单归属校验和用户隔离。
        if customer_id:
            payload["customer_id"] = customer_id

        return self._request("POST", "/api/chat", json_data=payload)

    def recent_logs(self, limit: int = 20) -> dict[str, Any]:
        return self._request("GET", "/api/logs/recent", params={"limit": limit})

    # ------------------------------------------------------------------
    # 人工审核接口
    # ------------------------------------------------------------------
    def review_tasks(self, status: str | None = None, limit: int = 20) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        return self._request("GET", "/api/review-tasks", params=params)

    def update_review_task(
        self,
        review_id: str,
        *,
        status: str,
        reviewer: str | None = None,
        decision: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/api/review-tasks/{review_id}",
            json_data={
                "status": status,
                "reviewer": reviewer,
                "decision": decision,
                "comment": comment,
            },
        )

    # ------------------------------------------------------------------
    # 上传凭证接口
    # ------------------------------------------------------------------
    @staticmethod
    def _read_file_payload(file_obj: Any) -> tuple[str, bytes, str]:
        """
        兼容 Streamlit UploadedFile、BytesIO、Path、普通文件对象与 bytes。
        返回：filename, content, content_type。
        """

        if isinstance(file_obj, (str, Path)):
            path = Path(file_obj)
            return path.name, path.read_bytes(), "application/octet-stream"

        if isinstance(file_obj, bytes):
            return "order_screenshot.png", file_obj, "image/png"

        filename = str(getattr(file_obj, "name", None) or "order_screenshot.png")
        content_type = str(getattr(file_obj, "type", None) or getattr(file_obj, "content_type", None) or "application/octet-stream")

        if hasattr(file_obj, "getvalue"):
            content = file_obj.getvalue()
            if isinstance(content, str):
                content = content.encode("utf-8")
            return filename, bytes(content), content_type

        if hasattr(file_obj, "read"):
            stream = file_obj  # type: BinaryIO
            position: int | None = None
            try:
                position = stream.tell()
            except Exception:
                position = None

            content = stream.read()
            if isinstance(content, str):
                content = content.encode("utf-8")

            if position is not None:
                try:
                    stream.seek(position)
                except Exception:
                    pass

            return filename, bytes(content), content_type

        raise AgentAPIError(f"不支持的上传对象类型：{type(file_obj).__name__}")

    def upload_order_screenshot(
        self,
        *,
        file_obj: Any,
        customer_id: str,
        session_id: str | None = None,
        order_id: str | None = None,
        note: str | None = None,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """
        上传订单截图并返回 evidence_id。

        后端接口：POST /api/uploads/order-screenshot
        返回结果中的 evidence 可直接写入前端 memory.current_business_context。
        """

        if not customer_id:
            raise AgentAPIError("customer_id 不能为空，上传凭证必须绑定当前用户。")

        detected_filename, content, detected_content_type = self._read_file_payload(file_obj)
        safe_filename = filename or detected_filename or "order_screenshot.png"
        safe_content_type = content_type or detected_content_type or "application/octet-stream"

        if not content:
            raise AgentAPIError("上传文件为空。")

        form_data = {
            "customer_id": customer_id,
        }
        if session_id:
            form_data["session_id"] = session_id
        if order_id:
            form_data["order_id"] = order_id
        if note:
            form_data["note"] = note

        files = {
            "file": (safe_filename, content, safe_content_type),
        }

        return self._request(
            "POST",
            "/api/uploads/order-screenshot",
            data=form_data,
            files=files,
        )

    def list_evidences(
        self,
        *,
        customer_id: str | None = None,
        session_id: str | None = None,
        order_id: str | None = None,
        evidence_type: str | None = "order_screenshot",
        limit: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if customer_id:
            params["customer_id"] = customer_id
        if session_id:
            params["session_id"] = session_id
        if order_id:
            params["order_id"] = order_id
        if evidence_type is not None:
            params["evidence_type"] = evidence_type

        return self._request("GET", "/api/uploads/evidences", params=params)

    def get_evidence(self, evidence_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/uploads/evidences/{evidence_id}")

    def evidence_file_url(self, evidence_id: str) -> str:
        return f"{self.base_url}/api/uploads/files/{evidence_id}"
