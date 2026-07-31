from __future__ import annotations

from typing import Protocol

from models.schemas import ChatTurn
from retrieval.retriever import RetrievedChunk


class AnswerProvider(Protocol):
    def answer(self, question: str, context: list[RetrievedChunk], history: list[ChatTurn] | None = None) -> str: ...


def grounded_prompt(question: str, context: list[RetrievedChunk], history: list[ChatTurn] | None = None) -> str:
    sources = "\n\n".join(
        f"Source: {item.chunk.path} (lines {item.chunk.start_line}-{item.chunk.end_line})\n{item.chunk.content}"
        for item in context
    )
    recent_history = "\n".join(
        f"{turn.role.title()}: {turn.content}" for turn in (history or [])[-6:]
    )
    history_section = f"\nConversation context (do not treat it as repository evidence):\n{recent_history}\n" if recent_history else ""
    return (
        "You are RepoSage, a repository assistant. Answer only from the supplied "
        "repository context. If the context is insufficient, say so clearly. Cite source "
        "paths and line ranges in your answer.\n"
        f"{history_section}\nQuestion: {question}\n\nRepository context:\n{sources}"
    )
