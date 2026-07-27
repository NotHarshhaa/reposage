"""FAISS-backed repository vector store."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from models.schemas import Chunk
from vectorstore.base import RemoteVectorStore, VectorMatch


class FaissVectorStore(RemoteVectorStore):
    def __init__(self, directory: Path, manifest_directory: Path) -> None:
        try:
            import faiss  # noqa: F401
            import numpy  # noqa: F401
        except ImportError as exc:  # pragma: no cover - guarded by optional dependency
            raise RuntimeError("FAISS requires faiss-cpu and numpy. Install backend requirements.") from exc
        super().__init__(manifest_directory)
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def _stem(self, repository_id: str) -> str:
        return hashlib.sha1(repository_id.encode("utf-8")).hexdigest()

    def _index_path(self, repository_id: str) -> Path:
        return self.directory / f"{self._stem(repository_id)}.faiss"

    def _chunks_path(self, repository_id: str) -> Path:
        return self.directory / f"{self._stem(repository_id)}.json"

    def _replace_chunks(self, repository_id: str, chunks: list[Chunk]) -> None:
        import faiss
        import numpy as np

        vectors = np.asarray([chunk.embedding for chunk in chunks], dtype="float32")
        if vectors.ndim != 2 or vectors.shape[1] == 0:
            raise ValueError("FAISS requires non-empty embeddings with a consistent dimension.")
        faiss.normalize_L2(vectors)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        faiss.write_index(index, str(self._index_path(repository_id)))
        destination = self._chunks_path(repository_id)
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps([chunk.model_dump() for chunk in chunks]), encoding="utf-8")
        temporary.replace(destination)

    def _load_chunks(self, repository_id: str) -> list[Chunk]:
        source = self._chunks_path(repository_id)
        if not source.exists():
            return []
        return [Chunk.model_validate(value) for value in json.loads(source.read_text(encoding="utf-8"))]

    def _search_chunks(self, repository_id: str, query_embedding: list[float], limit: int) -> list[VectorMatch]:
        import faiss
        import numpy as np

        index_path = self._index_path(repository_id)
        if not index_path.exists():
            return []
        chunks = self._load_chunks(repository_id)
        if not chunks:
            return []
        query = np.asarray([query_embedding], dtype="float32")
        if query.ndim != 2 or query.shape[1] != len(chunks[0].embedding):
            return []
        faiss.normalize_L2(query)
        scores, positions = faiss.read_index(str(index_path)).search(query, limit)
        return [
            VectorMatch(chunks[int(position)], float(score))
            for score, position in zip(scores[0], positions[0])
            if int(position) >= 0 and float(score) > 0
        ]

    def _delete_chunks(self, repository_id: str) -> None:
        self._index_path(repository_id).unlink(missing_ok=True)
        self._chunks_path(repository_id).unlink(missing_ok=True)
