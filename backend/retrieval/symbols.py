"""Lightweight symbol extraction used for code outline navigation.

This deliberately uses line-anchored patterns instead of per-language parsers: it
stays dependency-free, never executes repository code, and degrades to an empty
outline for unsupported languages rather than failing a request.
"""

from __future__ import annotations

import re

from models.schemas import SymbolEntry

_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"

_PATTERNS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "python": [
        ("class", re.compile(rf"^\s*class\s+(?P<name>{_IDENTIFIER})")),
        ("function", re.compile(rf"^\s*(?:async\s+)?def\s+(?P<name>{_IDENTIFIER})")),
    ],
    "javascript": [
        ("class", re.compile(rf"^\s*(?:export\s+)?class\s+(?P<name>{_IDENTIFIER})")),
        ("function", re.compile(rf"^\s*(?:export\s+)?(?:async\s+)?function\s+(?P<name>{_IDENTIFIER})")),
        ("function", re.compile(rf"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>{_IDENTIFIER})\s*=\s*(?:async\s*)?\(")),
    ],
    "go": [
        ("function", re.compile(rf"^\s*func\s+(?:\([^)]*\)\s*)?(?P<name>{_IDENTIFIER})")),
        ("type", re.compile(rf"^\s*type\s+(?P<name>{_IDENTIFIER})")),
    ],
    "rust": [
        ("function", re.compile(rf"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(?P<name>{_IDENTIFIER})")),
        ("struct", re.compile(rf"^\s*(?:pub\s+)?struct\s+(?P<name>{_IDENTIFIER})")),
        ("trait", re.compile(rf"^\s*(?:pub\s+)?trait\s+(?P<name>{_IDENTIFIER})")),
        ("impl", re.compile(rf"^\s*impl(?:<[^>]*>)?\s+(?P<name>{_IDENTIFIER})")),
    ],
    "java": [
        ("class", re.compile(rf"^\s*(?:public|private|protected)?\s*(?:final\s+|abstract\s+)?class\s+(?P<name>{_IDENTIFIER})")),
        ("interface", re.compile(rf"^\s*(?:public|private|protected)?\s*interface\s+(?P<name>{_IDENTIFIER})")),
    ],
    "markdown": [
        ("heading", re.compile(r"^#{1,4}\s+(?P<name>.+?)\s*$")),
    ],
}
_PATTERNS["typescript"] = _PATTERNS["javascript"] + [
    ("interface", re.compile(rf"^\s*(?:export\s+)?interface\s+(?P<name>{_IDENTIFIER})")),
    ("type", re.compile(rf"^\s*(?:export\s+)?type\s+(?P<name>{_IDENTIFIER})")),
]
_PATTERNS["csharp"] = _PATTERNS["java"]


def extract_symbols(content: str, language: str, limit: int = 400) -> list[SymbolEntry]:
    patterns = _PATTERNS.get(language.lower())
    if not patterns:
        return []
    symbols: list[SymbolEntry] = []
    for number, line in enumerate(content.splitlines(), start=1):
        if len(symbols) >= limit:
            break
        for kind, pattern in patterns:
            match = pattern.match(line)
            if match:
                name = match.group("name").strip()
                if name:
                    symbols.append(SymbolEntry(name=name[:200], kind=kind, line=number))
                break
    return symbols
