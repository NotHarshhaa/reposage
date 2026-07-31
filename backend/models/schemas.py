from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

RepositoryStatus = Literal["queued", "indexing", "ready", "failed", "cancelled"]


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


class LanguageBreakdown(BaseModel):
    language: str
    file_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    share: float = Field(ge=0, le=100)


class FileWeight(BaseModel):
    path: str
    language: str
    chunk_count: int = Field(ge=0)
    character_count: int = Field(ge=0)


class RepositoryInsights(BaseModel):
    repository_id: str
    owner: str
    name: str
    branch: str | None = None
    indexed_at: datetime
    file_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    total_characters: int = Field(ge=0)
    average_chunk_characters: int = Field(ge=0)
    languages: list[LanguageBreakdown]
    largest_files: list[FileWeight]
    documentation_files: list[str]


class SymbolEntry(BaseModel):
    name: str
    kind: str
    line: int = Field(ge=1)


class FileOutline(BaseModel):
    path: str
    language: str
    line_count: int = Field(ge=0)
    symbols: list[SymbolEntry]


class MultiSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2_000)
    limit_per_repository: int = Field(default=3, ge=1, le=10)
    repository_ids: list[str] = Field(default_factory=list, max_length=25)
    languages: list[str] = Field(default_factory=list, max_length=20)
    min_score: float = Field(default=0, ge=0, le=1)


class RepositoryMatches(BaseModel):
    repository_id: str
    owner: str
    name: str
    sources: list[SourceCitation]


class MultiSearchResult(BaseModel):
    query: str
    repositories: list[RepositoryMatches]


class SimilarCodeRequest(BaseModel):
    repository_id: str = Field(min_length=3, max_length=200)
    path: str = Field(min_length=1, max_length=500)
    line: int = Field(default=1, ge=1)
    limit: int = Field(default=5, ge=1, le=20)


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=16_000)
    sources: list[SourceCitation] = Field(default_factory=list)


class SaveConversationRequest(BaseModel):
    repository_id: str = Field(min_length=3, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    messages: list[ConversationMessage] = Field(min_length=1, max_length=200)


class Conversation(BaseModel):
    id: str
    repository_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = Field(ge=0)
    messages: list[ConversationMessage] = Field(default_factory=list)


class ConversationSummary(BaseModel):
    id: str
    repository_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = Field(ge=0)

    @classmethod
    def from_conversation(cls, conversation: "Conversation") -> "ConversationSummary":
        return cls(**conversation.model_dump(exclude={"messages"}))


class MetricsResponse(BaseModel):
    repositories_total: int = Field(ge=0)
    repositories_by_status: dict[str, int]
    files_indexed: int = Field(ge=0)
    chunks_indexed: int = Field(ge=0)
    active_index_jobs: int = Field(ge=0)
    conversations_saved: int = Field(ge=0)
    providers: dict[str, str]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    providers: dict[str, str]
