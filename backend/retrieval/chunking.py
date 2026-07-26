from __future__ import annotations

from ingestion.loader import SourceFile
from models.schemas import Chunk


def chunk_source_file(source: SourceFile, chunk_size: int, overlap: int) -> list[Chunk]:
    """Split source at line boundaries while preserving file and line references."""
    lines = source.content.splitlines()
    chunks: list[Chunk] = []
    start = 0
    chunk_number = 0
    while start < len(lines):
        end = start
        characters = 0
        while end < len(lines) and (characters + len(lines[end]) + 1 <= chunk_size or end == start):
            characters += len(lines[end]) + 1
            end += 1
        content = "\n".join(lines[start:end]).strip()
        if content:
            chunks.append(Chunk(
                id=f"{source.path}:{chunk_number}", path=source.path, content=content,
                start_line=start + 1, end_line=end, language=source.language,
            ))
            chunk_number += 1
        if end >= len(lines):
            break
        retained = 0
        next_start = end
        while next_start > start and retained < overlap:
            next_start -= 1
            retained += len(lines[next_start]) + 1
        start = next_start if next_start > start else end
    return chunks
