from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

RepositoryStatus = Literal["queued", "indexing", "ready", "failed"]


class IndexRepositoryRequest(BaseModel):
    url: HttpUrl = Field(description="GitHub repository URL")
    branch: str | None = Field(default=None, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    # Used only for this clone operation; it is never written to an index manifest.
    access_token: str | None = Field(default=None, min_length=1, max_length=512, repr=False)


class ReindexRepositoryRequest(BaseModel):
    branch: str | None = Field(default=None, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    access_token: str | None = Field(default=None, min_length=1, max_length=512, repr=False)


class Chunk(BaseModel):
    id: str
    path: str
    content: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    language: str
    embedding: list[float] = Field(default_factory=list)


class RepositoryIndex(BaseModel):
    id: str
    url: str
    owner: str
    name: str
    branch: str | None = None
    status: RepositoryStatus
    indexed_at: datetime
    updated_at: datetime | None = None
    progress: int = Field(default=0, ge=0, le=100)
    stage: str | None = None
    file_count: int
    chunk_count: int
    error: str | None = None
    chunks: list[Chunk] = Field(default_factory=list)


class RepositorySummary(BaseModel):
    id: str
    url: str
    owner: str
    name: str
    branch: str | None = None
    status: RepositoryStatus
    indexed_at: datetime
    updated_at: datetime | None = None
    progress: int = Field(default=0, ge=0, le=100)
    stage: str | None = None
    file_count: int
    chunk_count: int
    error: str | None = None

    @classmethod
    def from_index(cls, index: "RepositoryIndex") -> "RepositorySummary":
        return cls(**index.model_dump(exclude={"chunks"}))


class RepositoryFile(BaseModel):
    path: str
    language: str
    size_bytes: int = Field(ge=0)
    content: str | None = None


class SourceCitation(BaseModel):
    path: str
    start_line: int
    end_line: int
    score: float
    excerpt: str
    language: str | None = None


class SearchRequest(BaseModel):
    repository_id: str = Field(min_length=3, max_length=200)
    query: str = Field(min_length=2, max_length=2_000)
    limit: int = Field(default=6, ge=1, le=20)
    languages: list[str] = Field(default_factory=list, max_length=20)
    path_prefix: str | None = Field(default=None, max_length=500)
    min_score: float = Field(default=0, ge=0, le=1)


class SearchResult(BaseModel):
    query: str
    sources: list[SourceCitation]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8_000)


class ChatRequest(BaseModel):
    repository_id: str = Field(min_length=3, max_length=200)
    question: str = Field(min_length=2, max_length=2_000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    limit: int = Field(default=6, ge=1, le=12)
    languages: list[str] = Field(default_factory=list, max_length=20)
    path_prefix: str | None = Field(default=None, max_length=500)
    min_score: float = Field(default=0, ge=0, le=1)


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    providers: dict[str, str]
