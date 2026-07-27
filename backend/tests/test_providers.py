from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from config.settings import Settings
from embeddings.providers import (
    GeminiEmbeddingProvider, NomicEmbeddingProvider, OpenAIEmbeddingProvider, create_embedding_provider,
)
from llm.providers import GeminiAnswerProvider, OllamaAnswerProvider, OpenAIAnswerProvider, create_answer_provider
from models.schemas import Chunk, RepositoryIndex
from retrieval.retriever import RetrievedChunk
from vectorstore.factory import create_vector_store
from vectorstore.local_store import LocalVectorStore


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


def context() -> list[RetrievedChunk]:
    chunk = Chunk(
        id="readme:1", path="README.md", content="Run with uvicorn.", start_line=1,
        end_line=1, language="markdown", embedding=[1.0, 0.0],
    )
    return [RetrievedChunk(chunk, 0.9)]


def test_default_provider_factories_remain_local(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    assert create_embedding_provider(settings).__class__.__name__ == "HashEmbeddingProvider"
    assert create_answer_provider(settings).__class__.__name__ == "ExtractiveAnswerer"
    assert isinstance(create_vector_store(settings), LocalVectorStore)


@pytest.mark.parametrize(
    ("field", "value", "factory", "expected"),
    [
        ("embedding_provider", "openai", create_embedding_provider, OpenAIEmbeddingProvider),
        ("embedding_provider", "gemini", create_embedding_provider, GeminiEmbeddingProvider),
        ("embedding_provider", "nomic", create_embedding_provider, NomicEmbeddingProvider),
        ("llm_provider", "openai", create_answer_provider, OpenAIAnswerProvider),
        ("llm_provider", "gemini", create_answer_provider, GeminiAnswerProvider),
        ("llm_provider", "ollama", create_answer_provider, OllamaAnswerProvider),
    ],
)
def test_remote_provider_factories_select_requested_adapter(tmp_path, field, value, factory, expected) -> None:
    settings = Settings(
        data_dir=tmp_path, openai_api_key="openai-key", gemini_api_key="gemini-key", nomic_api_key="nomic-key",
        **{field: value},
    )
    assert isinstance(factory(settings), expected)


def test_selected_provider_requires_its_credential(tmp_path) -> None:
    with pytest.raises(ValueError, match="REPOSAGE_OPENAI_API_KEY"):
        create_embedding_provider(Settings(data_dir=tmp_path, embedding_provider="openai"))


def test_remote_adapters_parse_provider_responses(monkeypatch) -> None:
    responses = iter([
        {"data": [{"embedding": [0.1, 0.2]}]},
        {"embedding": {"values": [0.3, 0.4]}},
        {"embeddings": [[0.5, 0.6]]},
        {"choices": [{"message": {"content": "OpenAI answer"}}]},
        {"candidates": [{"content": {"parts": [{"text": "Gemini answer"}]}}]},
        {"response": "Ollama answer"},
    ])

    def fake_post(*args, **kwargs):
        return FakeResponse(next(responses))

    monkeypatch.setattr(httpx, "post", fake_post)
    assert OpenAIEmbeddingProvider("key", "model", "https://example.test/v1", 1).embed("text") == [0.1, 0.2]
    assert GeminiEmbeddingProvider("key", "model", "https://example.test/v1", 1).embed("text") == [0.3, 0.4]
    assert NomicEmbeddingProvider("key", "model", "https://example.test/v1", 1).embed("text") == [0.5, 0.6]
    assert OpenAIAnswerProvider("key", "model", "https://example.test/v1", 0, 1).answer("question", context()) == "OpenAI answer"
    assert GeminiAnswerProvider("key", "model", "https://example.test/v1", 0, 1).answer("question", context()) == "Gemini answer"
    assert OllamaAnswerProvider("model", "https://example.test", 0, 1).answer("question", context()) == "Ollama answer"


def test_bge_factory_uses_sentence_transformers_adapter(monkeypatch, tmp_path) -> None:
    import sys
    import types

    class FakeVector:
        def tolist(self):
            return [0.7, 0.8]

    class FakeModel:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def encode(self, text: str, normalize_embeddings: bool):
            assert text == "text"
            assert normalize_embeddings is True
            return FakeVector()

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeModel))
    provider = create_embedding_provider(Settings(data_dir=tmp_path, embedding_provider="bge"))
    assert provider.embed("text") == [0.7, 0.8]


def test_vector_store_factory_dispatches_without_connecting(monkeypatch, tmp_path) -> None:
    import vectorstore.factory as factory

    class FakeStore:
        def __init__(self, *args) -> None:
            self.args = args

    monkeypatch.setattr(factory, "QdrantVectorStore", FakeStore)
    monkeypatch.setattr(factory, "ChromaVectorStore", FakeStore)
    monkeypatch.setattr(factory, "FaissVectorStore", FakeStore)
    assert isinstance(create_vector_store(Settings(data_dir=tmp_path, vector_store_provider="qdrant")), FakeStore)
    assert isinstance(create_vector_store(Settings(data_dir=tmp_path, vector_store_provider="chroma")), FakeStore)
    assert isinstance(create_vector_store(Settings(data_dir=tmp_path, vector_store_provider="faiss")), FakeStore)



@pytest.mark.parametrize("provider", ["qdrant", "chroma", "faiss"])
def test_vector_backends_persist_and_search(provider, tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, vector_store_provider=provider, qdrant_url=":memory:")
    store = create_vector_store(settings)
    chunks = [
        Chunk(id="first", path="first.py", content="alpha", start_line=1, end_line=1, language="python", embedding=[1.0, 0.0]),
        Chunk(id="second", path="second.py", content="beta", start_line=1, end_line=1, language="python", embedding=[0.0, 1.0]),
    ]
    index = RepositoryIndex(
        id="acme-demo-123", url="https://github.com/acme/demo.git", owner="acme", name="demo",
        status="ready", indexed_at=datetime.now(UTC), file_count=2, chunk_count=2, chunks=chunks,
    )
    store.save(index)

    loaded = store.load(index.id)
    assert loaded is not None
    assert [chunk.id for chunk in loaded.chunks] == ["first", "second"]
    assert store.list()[0].id == index.id
    assert store.search(index.id, [1.0, 0.0], 1)[0].chunk.id == "first"
