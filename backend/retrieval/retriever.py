from __future__ import annotations

from dataclasses import dataclass

from embeddings.hashing import EmbeddingProvider
from models.schemas import Chunk, SourceCitation
from vectorstore.base import VectorMatch, cosine_similarity


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float


class Retriever:
    def __init__(self, embeddings: EmbeddingProvider) -> None:
        self.embeddings = embeddings

    def query_embedding(self, query: str) -> list[float]:
        return self.embeddings.embed(query)

    def search(self, chunks: list[Chunk], query: str, limit: int) -> list[RetrievedChunk]:
        query_embedding = self.query_embedding(query)
        matches = [VectorMatch(chunk, cosine_similarity(query_embedding, chunk.embedding)) for chunk in chunks]
        return self.from_matches(matches, limit)

    @staticmethod
    def from_matches(matches: list[VectorMatch], limit: int | None = None) -> list[RetrievedChunk]:
        relevant = [RetrievedChunk(item.chunk, item.score) for item in matches if item.score > 0]
        ranked = sorted(relevant, key=lambda item: item.score, reverse=True)
        return ranked if limit is None else ranked[:limit]

    @staticmethod
    def citations(results: list[RetrievedChunk]) -> list[SourceCitation]:
        return [SourceCitation(
            path=item.chunk.path, start_line=item.chunk.start_line, end_line=item.chunk.end_line,
            score=round(item.score, 3), excerpt=item.chunk.content[:700],
        ) for item in results]
