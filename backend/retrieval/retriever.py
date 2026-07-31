from __future__ import annotations

import re
from dataclasses import dataclass

from embeddings.hashing import EmbeddingProvider
from models.schemas import Chunk, SourceCitation
from vectorstore.base import VectorMatch, cosine_similarity

_WORDS = re.compile(r"[A-Za-z0-9_]{2,}")


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
        return self.rerank(matches, query, limit)

    @staticmethod
    def rerank(
        matches: list[VectorMatch], query: str, limit: int | None = None, languages: list[str] | None = None,
        path_prefix: str | None = None, min_score: float = 0,
    ) -> list[RetrievedChunk]:
        requested_languages = {language.lower().strip() for language in languages or [] if language.strip()}
        normalized_prefix = (path_prefix or "").replace("\\", "/").lstrip("/").lower()
        terms = set(_WORDS.findall(query.lower()))
        ranked: list[RetrievedChunk] = []
        for item in matches:
            chunk = item.chunk
            if requested_languages and chunk.language.lower() not in requested_languages:
                continue
            if normalized_prefix and not chunk.path.lower().startswith(normalized_prefix):
                continue
            haystack = f"{chunk.path}\n{chunk.content}".lower()
            lexical_hits = sum(1 for term in terms if term in haystack)
            lexical_score = lexical_hits / len(terms) if terms else 0
            score = round((item.score * 0.82) + (lexical_score * 0.18), 6)
            if score >= min_score and score > 0:
                ranked.append(RetrievedChunk(chunk, score))
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked if limit is None else ranked[:limit]

    @staticmethod
    def from_matches(matches: list[VectorMatch], limit: int | None = None) -> list[RetrievedChunk]:
        return Retriever.rerank(matches, "", limit)

    @staticmethod
    def citations(results: list[RetrievedChunk]) -> list[SourceCitation]:
        return [SourceCitation(
            path=item.chunk.path, start_line=item.chunk.start_line, end_line=item.chunk.end_line,
            score=round(item.score, 3), excerpt=item.chunk.content[:700], language=item.chunk.language,
        ) for item in results]
