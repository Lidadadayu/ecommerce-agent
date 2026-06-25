from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Protocol

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class TextEmbeddingV3Client:
    """
    OpenAI-compatible embedding client.

    默认面向 DashScope 兼容模式：
    - model: text-embedding-v3
    - base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        batch_size: int | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.model = model or os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
        self.api_key = api_key or os.getenv("EMBEDDING_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or os.getenv("EMBEDDING_BASE_URL") or os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        # DashScope text-embedding-v3 currently accepts at most 10 input texts
        # per request. Keep the client conservative by default so indexing works
        # out of the box with the configured model.
        self.batch_size = max(1, min(int(batch_size or _env_int("EMBEDDING_BATCH_SIZE", 10)), 10))
        self.timeout = timeout if timeout is not None else _env_float("EMBEDDING_TIMEOUT_SECONDS", 30.0)
        self.max_retries = max_retries if max_retries is not None else _env_int("EMBEDDING_MAX_RETRIES", 2)

    def _client(self):
        if not self.api_key:
            raise RuntimeError("EMBEDDING_API_KEY or DASHSCOPE_API_KEY is not set.")
        try:
            from openai import OpenAI
        except Exception as exc:
            raise RuntimeError("openai package is not installed. Please install openai first.") from exc
        return OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout, max_retries=0)

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = self._client()
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = client.embeddings.create(model=self.model, input=texts)
                vectors = [item.embedding for item in response.data]
                if len(vectors) != len(texts):
                    raise RuntimeError(f"Embedding count mismatch: expected {len(texts)}, got {len(vectors)}")
                return vectors
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(0.8 * (attempt + 1))
        raise RuntimeError(f"Embedding request failed: {last_error}") from last_error

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        clean_texts = [str(text or "").strip() for text in texts]
        if not clean_texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(clean_texts), self.batch_size):
            vectors.extend(self._embed_batch(clean_texts[start:start + self.batch_size]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_documents([text])
        if not vectors:
            raise RuntimeError("Query embedding is empty.")
        return vectors[0]


def get_embedding_client() -> TextEmbeddingV3Client:
    return TextEmbeddingV3Client()


def embedding_config() -> dict[str, Any]:
    client = TextEmbeddingV3Client()
    return {
        "model": client.model,
        "base_url": client.base_url,
        "batch_size": client.batch_size,
        "has_api_key": bool(client.api_key),
    }
