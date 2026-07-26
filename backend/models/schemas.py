from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class IndexRepositoryRequest(BaseModel):
    url: HttpUrl = Field(description="Public github.com repository URL")


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
    status: Literal["ready", "failed"]
    indexed_at: datetime
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
    status: Literal["ready", "failed"]
    indexed_at: datetime
    file_count: int
    chunk_count: int
    error: str | None = None

    @classmethod
    def from_index(cls, index: RepositoryIndex) -> "RepositorySummary":
        return cls(**index.model_dump(exclude={"chunks"}))


class SourceCitation(BaseModel):
    path: str
    start_line: int
    end_line: int
    score: float
    excerpt: str


class SearchRequest(BaseModel):
    repository_id: str = Field(min_length=3, max_length=200)
    query: str = Field(min_length=2, max_length=2_000)
    limit: int = Field(default=6, ge=1, le=20)


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


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
