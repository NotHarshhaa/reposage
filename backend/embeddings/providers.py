"""Concrete embedding providers selected by configuration."""

from __future__ import annotations

from typing import Any

import httpx

from embeddings.hashing import EmbeddingProvider


def _require(value: str | None, setting_name: str) -> str:
    if not value:
        raise ValueError(f"{setting_name} is required for the selected provider.")
    return value


def _embedding_from(payload: dict[str, Any], *paths: tuple[str, ...]) -> list[float]:
    for path in paths:
        value: Any = payload
        try:
            for key in path:
                value = value[key]
        except (KeyError, IndexError, TypeError):
            continue
        if isinstance(value, list) and value and all(isinstance(item, (float, int)) for item in value):
            return [float(item) for item in value]
    raise ValueError("The embedding provider returned an unexpected response format.")


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str | None, model: str, base_url: str, timeout: float) -> None:
        self.api_key = _require(api_key, "REPOSAGE_OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": text},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return _embedding_from(response.json(), ("data", 0, "embedding"))


class GeminiEmbeddingProvider:
    def __init__(self, api_key: str | None, model: str, base_url: str, timeout: float) -> None:
        self.api_key = _require(api_key, "REPOSAGE_GEMINI_API_KEY")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            f"{self.base_url}/models/{self.model}:embedContent",
            params={"key": self.api_key},
            json={"content": {"parts": [{"text": text}]}},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return _embedding_from(response.json(), ("embedding", "values"))


class BGEEmbeddingProvider:
    """Local BGE provider backed by sentence-transformers.

    The selected model is downloaded by sentence-transformers on first use unless it
    already exists in its local Hugging Face cache.
    """

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - guarded by optional dependency
            raise RuntimeError("BGE requires sentence-transformers. Install backend requirements.") from exc
        self.model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        vector = self.model.encode(text, normalize_embeddings=True)
        return [float(value) for value in vector.tolist()]


class NomicEmbeddingProvider:
    def __init__(self, api_key: str | None, model: str, base_url: str, timeout: float) -> None:
        self.api_key = _require(api_key, "REPOSAGE_NOMIC_API_KEY")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            f"{self.base_url}/embedding/text",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "texts": [text], "task_type": "search_document"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return _embedding_from(response.json(), ("embeddings", 0))


def create_embedding_provider(settings: Any) -> EmbeddingProvider:
    provider = settings.embedding_provider
    if provider == "hashing":
        from embeddings.hashing import HashEmbeddingProvider

        return HashEmbeddingProvider(settings.embedding_dimensions)
    if provider == "openai":
        return OpenAIEmbeddingProvider(settings.openai_api_key, settings.embedding_model, settings.openai_base_url, settings.provider_timeout_seconds)
    if provider == "gemini":
        return GeminiEmbeddingProvider(settings.gemini_api_key, settings.embedding_model, settings.gemini_base_url, settings.provider_timeout_seconds)
    if provider == "bge":
        return BGEEmbeddingProvider(settings.bge_model)
    if provider == "nomic":
        return NomicEmbeddingProvider(settings.nomic_api_key, settings.embedding_model, settings.nomic_base_url, settings.provider_timeout_seconds)
    raise ValueError(f"Unsupported embedding provider: {provider}")
