from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".go": "go", ".java": "java", ".cs": "csharp", ".rs": "rust",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".sh": "shell",
    ".tf": "terraform", ".yaml": "yaml", ".yml": "yaml", ".json": "json",
    ".md": "markdown", ".toml": "toml", ".ini": "ini", ".cfg": "config",
    ".xml": "xml", ".html": "html", ".css": "css", ".sql": "sql",
}
SPECIAL_FILENAMES = {
    "dockerfile": "dockerfile", "docker-compose.yml": "yaml", "docker-compose.yaml": "yaml",
    "makefile": "make", ".env.example": "environment", ".gitignore": "config",
}
IGNORED_DIRECTORIES = {".git", "node_modules", "vendor", "dist", "build", ".next", ".venv", "venv", "__pycache__", "coverage"}


@dataclass(frozen=True)
class SourceFile:
    path: str
    content: str
    language: str


def discover_source_files(root: Path, max_file_size: int, max_files: int) -> list[SourceFile]:
    files: list[SourceFile] = []
    for candidate in root.rglob("*"):
        if len(files) >= max_files:
            break
        if not candidate.is_file() or any(part in IGNORED_DIRECTORIES for part in candidate.parts):
            continue
        language = SPECIAL_FILENAMES.get(candidate.name.lower()) or SUPPORTED_EXTENSIONS.get(candidate.suffix.lower())
        if not language or candidate.stat().st_size > max_file_size:
            continue
        try:
            content = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if content.strip():
            files.append(SourceFile(candidate.relative_to(root).as_posix(), content, language))
    return files
