"""Remote LLM answer providers selected by configuration."""

from __future__ import annotations

from typing import Any

import httpx

from llm.base import AnswerProvider, grounded_prompt
from retrieval.retriever import RetrievedChunk


def _require(value: str | None, setting_name: str) -> str:
    if not value:
        raise ValueError(f"{setting_name} is required for the selected provider.")
    return value


def _text(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list):
        text = "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in value)
        if text.strip():
            return text.strip()
    raise ValueError("The LLM provider returned an empty or unexpected response.")


class OpenAIAnswerProvider:
    def __init__(self, api_key: str | None, model: str, base_url: str, temperature: float, timeout: float) -> None:
        self.api_key = _require(api_key, "REPOSAGE_OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout

    def answer(self, question: str, context: list[RetrievedChunk]) -> str:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": self.temperature,
                "messages": [{"role": "user", "content": grounded_prompt(question, context)}],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return _text(response.json()["choices"][0]["message"]["content"])


class GeminiAnswerProvider:
    def __init__(self, api_key: str | None, model: str, base_url: str, temperature: float, timeout: float) -> None:
        self.api_key = _require(api_key, "REPOSAGE_GEMINI_API_KEY")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout

    def answer(self, question: str, context: list[RetrievedChunk]) -> str:
        response = httpx.post(
            f"{self.base_url}/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json={
                "contents": [{"role": "user", "parts": [{"text": grounded_prompt(question, context)}]}],
                "generationConfig": {"temperature": self.temperature},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        parts = response.json()["candidates"][0]["content"]["parts"]
        return _text(parts)


class OllamaAnswerProvider:
    def __init__(self, model: str, base_url: str, temperature: float, timeout: float) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout

    def answer(self, question: str, context: list[RetrievedChunk]) -> str:
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": grounded_prompt(question, context),
                "stream": False,
                "options": {"temperature": self.temperature},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return _text(response.json().get("response"))


def create_answer_provider(settings: Any) -> AnswerProvider:
    provider = settings.llm_provider
    if provider == "extractive":
        from llm.extractive import ExtractiveAnswerer

        return ExtractiveAnswerer()
    if provider == "openai":
        return OpenAIAnswerProvider(settings.openai_api_key, settings.llm_model, settings.openai_base_url, settings.llm_temperature, settings.provider_timeout_seconds)
    if provider == "gemini":
        return GeminiAnswerProvider(settings.gemini_api_key, settings.llm_model, settings.gemini_base_url, settings.llm_temperature, settings.provider_timeout_seconds)
    if provider == "ollama":
        return OllamaAnswerProvider(settings.llm_model, settings.ollama_base_url, settings.llm_temperature, settings.provider_timeout_seconds)
    raise ValueError(f"Unsupported LLM provider: {provider}")
