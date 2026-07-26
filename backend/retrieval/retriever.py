from __future__ import annotations

from dataclasses import dataclass

from embeddings.hashing import EmbeddingProvider
from models.schemas import Chunk, SourceCitation
from vectorstore.local_store import LocalVectorStore


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float


class Retriever:
    def __init__(self, embeddings: EmbeddingProvider) -> None:
        self.embeddings = embeddings

    def search(self, chunks: list[Chunk], query: str, limit: int) -> list[RetrievedChunk]:
        query_embedding = self.embeddings.embed(query)
        ranked = [RetrievedChunk(chunk, LocalVectorStore.cosine_similarity(query_embedding, chunk.embedding)) for chunk in chunks]
        # A score of zero indicates no shared embedded features and is not useful context.
        results = [item for item in ranked if item.score > 0]
        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]

    @staticmethod
    def citations(results: list[RetrievedChunk]) -> list[SourceCitation]:
        return [SourceCitation(
            path=item.chunk.path, start_line=item.chunk.start_line, end_line=item.chunk.end_line,
            score=round(item.score, 3), excerpt=item.chunk.content[:700],
        ) for item in results]
