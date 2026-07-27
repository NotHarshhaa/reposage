from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from config.settings import Settings
from embeddings.factory import create_embedding_provider
from ingestion.github import GitHubRepository, clone_repository, parse_public_github_url
from ingestion.loader import discover_source_files
from llm.factory import create_answer_provider
from models.schemas import ChatResponse, RepositoryIndex, RepositorySummary, SearchResult
from retrieval.chunking import chunk_source_file
from retrieval.retriever import Retriever
from vectorstore.factory import create_vector_store


class RepositoryNotFoundError(LookupError):
    pass


class RepositoryService:
    def __init__(self, settings: Settings) -> None:
        settings.ensure_directories()
        self.settings = settings
        self.embeddings = create_embedding_provider(settings)
        self.store = create_vector_store(settings)
        self.retriever = Retriever(self.embeddings)
        self.answerer = create_answer_provider(settings)

    def index_repository(self, url: str) -> RepositorySummary:
        repository = parse_public_github_url(url)
        try:
            branch = clone_repository(repository, self._repository_path(repository))
            files = discover_source_files(
                self._repository_path(repository), self.settings.max_file_size_bytes,
                self.settings.max_repository_files,
            )
            chunks = []
            for source in files:
                for chunk in chunk_source_file(source, self.settings.chunk_size, self.settings.chunk_overlap):
                    chunk.embedding = self.embeddings.embed(f"{chunk.path}\n{chunk.content}")
                    chunks.append(chunk)
            if not chunks:
                raise ValueError("No supported, non-empty source or documentation files were found.")
            index = RepositoryIndex(
                id=repository.id, url=repository.url, owner=repository.owner, name=repository.name,
                branch=branch, status="ready", indexed_at=datetime.now(UTC),
                file_count=len(files), chunk_count=len(chunks), chunks=chunks,
            )
        except Exception as exc:
            index = RepositoryIndex(
                id=repository.id, url=repository.url, owner=repository.owner, name=repository.name,
                status="failed", indexed_at=datetime.now(UTC), file_count=0, chunk_count=0,
                error=str(exc), chunks=[],
            )
        self.store.save(index)
        return RepositorySummary.from_index(index)

    def list_repositories(self) -> list[RepositorySummary]:
        return [RepositorySummary.from_index(index) for index in self.store.list()]

    def get_repository(self, repository_id: str) -> RepositorySummary:
        return RepositorySummary.from_index(self._ready_index(repository_id))

    def search(self, repository_id: str, query: str, limit: int) -> SearchResult:
        self._ready_index(repository_id)
        results = self._retrieve(repository_id, query, limit)
        return SearchResult(query=query, sources=self.retriever.citations(results))

    def chat(self, repository_id: str, question: str, limit: int) -> ChatResponse:
        self._ready_index(repository_id)
        context = self._retrieve(repository_id, question, limit)
        return ChatResponse(answer=self.answerer.answer(question, context), sources=self.retriever.citations(context))

    def _retrieve(self, repository_id: str, query: str, limit: int):
        query_embedding = self.retriever.query_embedding(query)
        return self.retriever.from_matches(self.store.search(repository_id, query_embedding, limit))

    def _ready_index(self, repository_id: str) -> RepositoryIndex:
        index = self.store.load(repository_id)
        if not index:
            raise RepositoryNotFoundError("The repository has not been indexed yet.")
        if index.status != "ready":
            raise ValueError(index.error or "Repository indexing failed.")
        return index

    def _repository_path(self, repository: GitHubRepository) -> Path:
        return self.settings.data_dir / "repos" / repository.id
