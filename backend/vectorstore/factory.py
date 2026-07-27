from __future__ import annotations

from typing import Any

from vectorstore.base import VectorStore
from vectorstore.chroma_store import ChromaVectorStore
from vectorstore.faiss_store import FaissVectorStore
from vectorstore.local_store import LocalVectorStore
from vectorstore.qdrant_store import QdrantVectorStore


def create_vector_store(settings: Any) -> VectorStore:
    provider = settings.vector_store_provider
    manifest_directory = settings.data_dir / "indexes"
    if provider == "local":
        return LocalVectorStore(manifest_directory)
    if provider == "qdrant":
        return QdrantVectorStore(
            settings.qdrant_url, settings.qdrant_api_key, settings.qdrant_collection_prefix, manifest_directory
        )
    if provider == "chroma":
        return ChromaVectorStore(settings.resolved_chroma_path, manifest_directory)
    if provider == "faiss":
        return FaissVectorStore(settings.resolved_faiss_path, manifest_directory)
    raise ValueError(f"Unsupported vector store provider: {provider}")
