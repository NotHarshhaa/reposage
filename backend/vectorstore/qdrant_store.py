"""Qdrant-backed repository vector store."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from models.schemas import Chunk
from vectorstore.base import RemoteVectorStore, VectorMatch


class QdrantVectorStore(RemoteVectorStore):
    def __init__(self, url: str, api_key: str | None, collection_prefix: str, manifest_directory: Path) -> None:
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:  # pragma: no cover - guarded by optional dependency
            raise RuntimeError("Qdrant requires qdrant-client. Install backend requirements.") from exc
        super().__init__(manifest_directory)
        self.client = QdrantClient(location=":memory:") if url == ":memory:" else QdrantClient(url=url, api_key=api_key)
        self.collection_prefix = collection_prefix

    def _collection(self, repository_id: str) -> str:
        digest = hashlib.sha1(repository_id.encode("utf-8")).hexdigest()[:20]
        return f"{self.collection_prefix}-{digest}"

    @staticmethod
    def _payload(chunk: Chunk, position: int) -> dict[str, Any]:
        return {
            "id": chunk.id,
            "path": chunk.path,
            "content": chunk.content,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "language": chunk.language,
            "position": position,
        }

    @staticmethod
    def _chunk(payload: dict[str, Any]) -> Chunk:
        return Chunk(
            id=str(payload["id"]), path=str(payload["path"]), content=str(payload["content"]),
            start_line=int(payload["start_line"]), end_line=int(payload["end_line"]),
            language=str(payload["language"]),
        )

    def _replace_chunks(self, repository_id: str, chunks: list[Chunk]) -> None:
        from qdrant_client import models

        collection = self._collection(repository_id)
        try:
            self.client.delete_collection(collection)
        except Exception:
            pass
        self.client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=len(chunks[0].embedding), distance=models.Distance.COSINE),
        )
        points = [
            models.PointStruct(id=position, vector=chunk.embedding, payload=self._payload(chunk, position))
            for position, chunk in enumerate(chunks)
        ]
        self.client.upsert(collection_name=collection, points=points, wait=True)

    def _load_chunks(self, repository_id: str) -> list[Chunk]:
        collection = self._collection(repository_id)
        chunks: list[tuple[int, Chunk]] = []
        offset: str | int | None = None
        while True:
            records, offset = self.client.scroll(
                collection_name=collection, offset=offset, limit=256, with_payload=True, with_vectors=False
            )
            chunks.extend((int(record.payload["position"]), self._chunk(record.payload)) for record in records if record.payload)
            if offset is None:
                break
        return [chunk for _, chunk in sorted(chunks, key=lambda item: item[0])]

    def _search_chunks(self, repository_id: str, query_embedding: list[float], limit: int) -> list[VectorMatch]:
        response = self.client.query_points(
            collection_name=self._collection(repository_id), query=query_embedding, limit=limit, with_payload=True
        )
        return [
            VectorMatch(self._chunk(point.payload), float(point.score))
            for point in response.points if point.payload and float(point.score) > 0
        ]

    def _delete_chunks(self, repository_id: str) -> None:
        try:
            self.client.delete_collection(self._collection(repository_id))
        except Exception:
            pass
