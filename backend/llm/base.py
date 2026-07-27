from __future__ import annotations

from typing import Protocol

from retrieval.retriever import RetrievedChunk


class AnswerProvider(Protocol):
    def answer(self, question: str, context: list[RetrievedChunk]) -> str: ...


def grounded_prompt(question: str, context: list[RetrievedChunk]) -> str:
    sources = "\n\n".join(
        f"Source: {item.chunk.path} (lines {item.chunk.start_line}-{item.chunk.end_line})\n{item.chunk.content}"
        for item in context
    )
    return (
        "You are RepoSage, a repository assistant. Answer only from the supplied "
        "repository context. If the context is insufficient, say so clearly. Cite source "
        "paths and line ranges in your answer.\n\n"
        f"Question: {question}\n\nRepository context:\n{sources}"
    )
