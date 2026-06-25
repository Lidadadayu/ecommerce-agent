from __future__ import annotations

import json
import os
from typing import Any, Iterator

import requests


DEFAULT_API_BASE_URL = os.getenv("AGENT_API_BASE_URL", "http://127.0.0.1:8001")


class AgentStreamError(RuntimeError):
    pass


class AgentStreamClient:
    def __init__(self, base_url: str | None = None, timeout: int = 180) -> None:
        self.base_url = (base_url or DEFAULT_API_BASE_URL).rstrip("/")
        self.timeout = timeout

    def stream_chat(
        self,
        user_query: str,
        *,
        memory: dict[str, Any] | None = None,
        session_id: str | None = None,
        customer_id: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        url = f"{self.base_url}/api/chat/stream"
        payload: dict[str, Any] = {
            "user_query": user_query,
            "memory": memory or {},
            "session_id": session_id,
            "customer_id": customer_id,
        }

        try:
            with requests.post(url, json=payload, stream=True, timeout=self.timeout) as response:
                if response.status_code >= 400:
                    try:
                        detail = response.json()
                    except Exception:
                        detail = response.text
                    raise AgentStreamError(f"流式接口返回错误 {response.status_code}: {detail}")

                event_name = "message"
                data_lines: list[str] = []

                for raw_line in response.iter_lines(decode_unicode=True):
                    if raw_line is None:
                        continue

                    line = raw_line.strip("\r")

                    if line == "":
                        if data_lines:
                            data_text = "\n".join(data_lines)
                            try:
                                data = json.loads(data_text)
                            except json.JSONDecodeError:
                                data = {"raw": data_text}
                            if isinstance(data, dict):
                                data["event"] = event_name
                                yield data
                        event_name = "message"
                        data_lines = []
                        continue

                    if line.startswith("event:"):
                        event_name = line[len("event:"):].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[len("data:"):].strip())

                if data_lines:
                    data_text = "\n".join(data_lines)
                    try:
                        data = json.loads(data_text)
                    except json.JSONDecodeError:
                        data = {"raw": data_text}
                    if isinstance(data, dict):
                        data["event"] = event_name
                        yield data

        except requests.RequestException as exc:
            raise AgentStreamError(f"无法连接流式 Agent API：{exc}") from exc
