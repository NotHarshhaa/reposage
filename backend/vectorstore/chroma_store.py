"""Chroma-backed repository vector store."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from models.schemas import Chunk
from vectorstore.base import RemoteVectorStore, VectorMatch


class ChromaVectorStore(RemoteVectorStore):
    def __init__(self, path: Path, manifest_directory: Path) -> None:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - guarded by optional dependency
            raise RuntimeError("Chroma requires chromadb. Install backend requirements.") from exc
        super().__init__(manifest_directory)
        path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(path))

    @staticmethod
    def _collection(repository_id: str) -> str:
        return f"reposage_{hashlib.sha1(repository_id.encode('utf-8')).hexdigest()[:20]}"

    @staticmethod
    def _metadata(chunk: Chunk, position: int) -> dict[str, str | int]:
        return {
            "chunk_id": chunk.id, "path": chunk.path, "start_line": chunk.start_line,
            "end_line": chunk.end_line, "language": chunk.language, "position": position,
        }

    @staticmethod
    def _chunk(chunk_id: str, document: str, metadata: dict[str, Any]) -> Chunk:
        return Chunk(
            id=str(metadata.get("chunk_id", chunk_id)), path=str(metadata["path"]), content=document,
            start_line=int(metadata["start_line"]), end_line=int(metadata["end_line"]),
            language=str(metadata["language"]),
        )

    def _replace_chunks(self, repository_id: str, chunks: list[Chunk]) -> None:
        name = self._collection(repository_id)
        try:
            self.client.delete_collection(name)
        except Exception:
            pass
        collection = self.client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})
        collection.upsert(
            ids=[str(position) for position in range(len(chunks))],
            embeddings=[chunk.embedding for chunk in chunks],
            documents=[chunk.content for chunk in chunks],
            metadatas=[self._metadata(chunk, position) for position, chunk in enumerate(chunks)],
        )

    def _load_chunks(self, repository_id: str) -> list[Chunk]:
        collection = self.client.get_collection(name=self._collection(repository_id))
        result = collection.get(include=["documents", "metadatas"])
        entries = [
            (int(metadata["position"]), self._chunk(chunk_id, document, metadata))
            for chunk_id, document, metadata in zip(result["ids"], result["documents"], result["metadatas"])
            if document is not None and metadata is not None
        ]
        return [chunk for _, chunk in sorted(entries, key=lambda item: item[0])]

    def _search_chunks(self, repository_id: str, query_embedding: list[float], limit: int) -> list[VectorMatch]:
        collection = self.client.get_collection(name=self._collection(repository_id))
        result = collection.query(
            query_embeddings=[query_embedding], n_results=limit, include=["documents", "metadatas", "distances"]
        )
        return [
            VectorMatch(self._chunk(chunk_id, document, metadata), max(0.0, 1.0 - float(distance)))
            for chunk_id, document, metadata, distance in zip(
                result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
            )
            if document is not None and metadata is not None and distance is not None and float(distance) < 1.0
        ]

    def _delete_chunks(self, repository_id: str) -> None:
        try:
            self.client.delete_collection(self._collection(repository_id))
        except Exception:
            pass
