from __future__ import annotations

from retrieval.retriever import RetrievedChunk


class ExtractiveAnswerer:
    """Grounded fallback answerer that never invents repository details.

    A remote LLM adapter can replace this class. Keeping the fallback means a new
    installation has useful search-and-explain behavior without sending source
    code to a third-party API or requiring a key.
    """

    def answer(self, question: str, context: list[RetrievedChunk]) -> str:
        if not context:
            return (
                "I couldn't find relevant indexed source for that question. Try using "
                "specific names from the repository, or re-index the repository."
            )
        snippets: list[str] = []
        for item in context[:4]:
            lines = [line.strip() for line in item.chunk.content.splitlines() if line.strip()]
            preview = " ".join(lines[:3])[:360]
            snippets.append(f"- `{item.chunk.path}` (lines {item.chunk.start_line}-{item.chunk.end_line}): {preview}")
        return (
            f"Here is the most relevant indexed context for: **{question}**\n\n"
            + "\n".join(snippets)
            + "\n\nUse the source references below to inspect the complete implementation."
        )
