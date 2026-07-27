"""Small persisted vector-store adapter backed by JSON index files."""

from __future__ import annotations

import json
from pathlib import Path

from models.schemas import RepositoryIndex
from vectorstore.base import VectorMatch, cosine_similarity


class LocalVectorStore:
    def __init__(self, index_directory: Path) -> None:
        self.index_directory = index_directory
        self.index_directory.mkdir(parents=True, exist_ok=True)

    def save(self, index: RepositoryIndex) -> None:
        destination = self.index_directory / f"{index.id}.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(index.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(destination)

    def load(self, repository_id: str) -> RepositoryIndex | None:
        source = self.index_directory / f"{repository_id}.json"
        if not source.exists():
            return None
        return RepositoryIndex.model_validate_json(source.read_text(encoding="utf-8"))

    def list(self) -> list[RepositoryIndex]:
        indexes: list[RepositoryIndex] = []
        for source in self.index_directory.glob("*.json"):
            try:
                indexes.append(RepositoryIndex.model_validate_json(source.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        return sorted(indexes, key=lambda index: index.indexed_at, reverse=True)

    def search(self, repository_id: str, query_embedding: list[float], limit: int) -> list[VectorMatch]:
        index = self.load(repository_id)
        if not index:
            return []
        ranked = [VectorMatch(chunk, cosine_similarity(query_embedding, chunk.embedding)) for chunk in index.chunks]
        return sorted((item for item in ranked if item.score > 0), key=lambda item: item.score, reverse=True)[:limit]

    @staticmethod
    def cosine_similarity(left: list[float], right: list[float]) -> float:
        return cosine_similarity(left, right)
