"""Small persisted vector-store adapter backed by JSON index files."""

from __future__ import annotations

import json
import math
from pathlib import Path

from models.schemas import RepositoryIndex


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

    @staticmethod
    def cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        denominator = math.sqrt(sum(v * v for v in left)) * math.sqrt(sum(v * v for v in right))
        return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0
