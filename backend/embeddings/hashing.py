"""Deterministic, dependency-free embedding adapter for local development."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_./-]*")


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(text)]


class HashEmbeddingProvider:
    """Feature-hashing embedding provider.

    It is intentionally local and deterministic, making the app usable before an
    external embedding API is configured. Swap this adapter for OpenAI, Gemini,
    BGE, or Nomic in a production deployment without changing retrieval code.
    """

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = tokenize(text)
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimensions
            sign = 1.0 if (value >> 8) & 1 else -1.0
            vector[index] += sign
        magnitude = math.sqrt(sum(value * value for value in vector))
        return [value / magnitude for value in vector] if magnitude else vector
