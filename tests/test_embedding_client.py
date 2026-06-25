from __future__ import annotations

from rag.embedding_client import TextEmbeddingV3Client


class _FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def create(self, *, model: str, input: list[str]):
        self.calls.append(input)

        class _Item:
            def __init__(self, value: float) -> None:
                self.embedding = [value, value + 1.0]

        class _Response:
            data = [_Item(float(i)) for i in range(len(input))]

        return _Response()


class _FakeClient:
    def __init__(self, embeddings: _FakeEmbeddings) -> None:
        self.embeddings = embeddings


def test_text_embedding_v3_client_batches_and_embeds(monkeypatch) -> None:
    fake_embeddings = _FakeEmbeddings()
    client = TextEmbeddingV3Client(api_key="test", batch_size=2, max_retries=0)
    monkeypatch.setattr(client, "_client", lambda: _FakeClient(fake_embeddings))

    vectors = client.embed_documents(["a", "b", "c"])

    assert len(vectors) == 3
    assert fake_embeddings.calls == [["a", "b"], ["c"]]


def test_text_embedding_v3_client_embeds_query(monkeypatch) -> None:
    fake_embeddings = _FakeEmbeddings()
    client = TextEmbeddingV3Client(api_key="test", batch_size=2, max_retries=0)
    monkeypatch.setattr(client, "_client", lambda: _FakeClient(fake_embeddings))

    vector = client.embed_query("hello")

    assert vector == [0.0, 1.0]
    assert fake_embeddings.calls == [["hello"]]
