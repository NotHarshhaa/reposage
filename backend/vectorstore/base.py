"""Shared vector-store contracts and metadata persistence for all providers."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from models.schemas import Chunk, RepositoryIndex


@dataclass(frozen=True)
class VectorMatch:
    chunk: Chunk
    score: float


class VectorStore(Protocol):
    def save(self, index: RepositoryIndex) -> None: ...
    def load(self, repository_id: str) -> RepositoryIndex | None: ...
    def list(self) -> list[RepositoryIndex]: ...
    def delete(self, repository_id: str) -> None: ...
    def search(self, repository_id: str, query_embedding: list[float], limit: int) -> list[VectorMatch]: ...


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


class IndexManifestStore:
    """Persists repository metadata for remote stores without duplicating vectors."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, index: RepositoryIndex) -> None:
        destination = self.directory / f"{index.id}.json"
        temporary = destination.with_suffix(".tmp")
        metadata = index.model_copy(update={"chunks": []})
        temporary.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(destination)

    def load(self, repository_id: str) -> RepositoryIndex | None:
        source = self.directory / f"{repository_id}.json"
        if not source.exists():
            return None
        return RepositoryIndex.model_validate_json(source.read_text(encoding="utf-8"))

    def list(self) -> list[RepositoryIndex]:
        indexes: list[RepositoryIndex] = []
        for source in self.directory.glob("*.json"):
            try:
                indexes.append(RepositoryIndex.model_validate_json(source.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        return sorted(indexes, key=lambda index: index.indexed_at, reverse=True)

    def delete(self, repository_id: str) -> None:
        (self.directory / f"{repository_id}.json").unlink(missing_ok=True)


class RemoteVectorStore:
    """Base implementation that keeps index metadata locally and vectors remotely."""

    def __init__(self, manifest_directory: Path) -> None:
        self.manifest = IndexManifestStore(manifest_directory)

    def save(self, index: RepositoryIndex) -> None:
        if index.status == "ready":
            if not index.chunks:
                raise ValueError("Cannot save a ready repository index without chunks.")
            self._replace_chunks(index.id, index.chunks)
        self.manifest.save(index)

    def load(self, repository_id: str) -> RepositoryIndex | None:
        index = self.manifest.load(repository_id)
        if not index or index.status != "ready":
            return index
        return index.model_copy(update={"chunks": self._load_chunks(repository_id)})

    def list(self) -> list[RepositoryIndex]:
        return self.manifest.list()

    def delete(self, repository_id: str) -> None:
        self._delete_chunks(repository_id)
        self.manifest.delete(repository_id)

    def search(self, repository_id: str, query_embedding: list[float], limit: int) -> list[VectorMatch]:
        return self._search_chunks(repository_id, query_embedding, limit)

    def _replace_chunks(self, repository_id: str, chunks: list[Chunk]) -> None:
        raise NotImplementedError

    def _load_chunks(self, repository_id: str) -> list[Chunk]:
        raise NotImplementedError

    def _search_chunks(self, repository_id: str, query_embedding: list[float], limit: int) -> list[VectorMatch]:
        raise NotImplementedError

    def _delete_chunks(self, repository_id: str) -> None:
        raise NotImplementedError
