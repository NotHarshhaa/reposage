from __future__ import annotations

import json
import shutil
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from config.settings import Settings
from embeddings.factory import create_embedding_provider
from ingestion.github import GitHubRepository, clone_repository, parse_public_github_url
from ingestion.loader import discover_source_files
from llm.factory import create_answer_provider
from models.schemas import (
    ChatResponse, ChatTurn, RepositoryFile, RepositoryIndex, RepositorySummary, SearchResult,
)
from retrieval.chunking import chunk_source_file
from retrieval.retriever import Retriever
from vectorstore.factory import create_vector_store


class RepositoryNotFoundError(LookupError):
    pass


class RepositoryBusyError(RuntimeError):
    pass


class RepositoryService:
    """Coordinates durable repository jobs and retrieval without a separate queue service."""

    def __init__(self, settings: Settings) -> None:
        settings.ensure_directories()
        self.settings = settings
        self.embeddings = create_embedding_provider(settings)
        self.store = create_vector_store(settings)
        self.retriever = Retriever(self.embeddings)
        self.answerer = create_answer_provider(settings)
        self._lock = threading.RLock()
        self._jobs: dict[str, Future[None]] = {}
        self._executor = ThreadPoolExecutor(max_workers=settings.index_workers, thread_name_prefix="reposage-index")

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def recover_interrupted_jobs(self) -> int:
        """Fail indexes left pending by a previous process so they can be retried."""
        recovered = 0
        with self._lock:
            for index in self.store.list():
                if index.status not in {"queued", "indexing"} or self._jobs.get(index.id):
                    continue
                self.store.save(index.model_copy(update={
                    "status": "failed", "stage": "Indexing interrupted",
                    "error": "Indexing was interrupted before completion. Re-index to try again.",
                    "updated_at": datetime.now(UTC), "chunks": [],
                }))
                recovered += 1
        return recovered

    def start_indexing(self, url: str, branch: str | None = None, access_token: str | None = None) -> RepositorySummary:
        repository = parse_public_github_url(url)
        if branch and (".." in branch or branch.startswith("/")):
            raise ValueError("Branch names cannot contain '..' or start with '/'.")
        with self._lock:
            current = self.store.load(repository.id)
            active_job = self._jobs.get(repository.id)
            if active_job and not active_job.done():
                existing = current or self._queued_index(repository, branch)
                return RepositorySummary.from_index(existing)
            now = datetime.now(UTC)
            queued = RepositoryIndex(
                id=repository.id, url=repository.url, owner=repository.owner, name=repository.name,
                branch=branch, status="queued", indexed_at=now, updated_at=now, progress=0,
                stage="Queued for indexing", file_count=0, chunk_count=0, chunks=[],
            )
            self.store.save(queued)
            self._jobs[repository.id] = self._executor.submit(self._index_job, repository, branch, access_token, now)
            return RepositorySummary.from_index(queued)

    def reindex_repository(self, repository_id: str, branch: str | None = None, access_token: str | None = None) -> RepositorySummary:
        index = self._get_index(repository_id)
        return self.start_indexing(index.url, branch or index.branch, access_token)

    def delete_repository(self, repository_id: str) -> None:
        with self._lock:
            self._get_index(repository_id)
            job = self._jobs.get(repository_id)
            if job and not job.done():
                raise RepositoryBusyError("The repository is currently indexing. Wait for it to finish before deleting it.")
            self.store.delete(repository_id)
            shutil.rmtree(self.settings.data_dir / "repos" / repository_id, ignore_errors=True)
            self._jobs.pop(repository_id, None)

    def list_repositories(self) -> list[RepositorySummary]:
        with self._lock:
            return [RepositorySummary.from_index(index) for index in self.store.list()]

    def get_repository(self, repository_id: str) -> RepositorySummary:
        return RepositorySummary.from_index(self._get_index(repository_id))

    def list_files(self, repository_id: str) -> list[RepositoryFile]:
        self._ready_index(repository_id)
        root = self._repository_path_from_id(repository_id)
        return [
            RepositoryFile(path=item.path, language=item.language, size_bytes=len(item.content.encode("utf-8")))
            for item in discover_source_files(root, self.settings.max_file_size_bytes, self.settings.max_repository_files)
        ]

    def read_file(self, repository_id: str, path: str) -> RepositoryFile:
        self._ready_index(repository_id)
        normalized = path.replace("\\", "/").lstrip("/")
        root = self._repository_path_from_id(repository_id).resolve()
        candidate = (root / normalized).resolve()
        if root not in candidate.parents or not candidate.is_file():
            raise RepositoryNotFoundError("The requested repository file was not found.")
        supported = {item.path: item for item in discover_source_files(root, self.settings.max_file_size_bytes, self.settings.max_repository_files)}
        source = supported.get(normalized)
        if not source:
            raise RepositoryNotFoundError("The requested file is not available for source browsing.")
        return RepositoryFile(
            path=source.path, language=source.language, size_bytes=len(source.content.encode("utf-8")), content=source.content,
        )

    def search(
        self, repository_id: str, query: str, limit: int, languages: list[str] | None = None,
        path_prefix: str | None = None, min_score: float = 0,
    ) -> SearchResult:
        self._ready_index(repository_id)
        results = self._retrieve(repository_id, query, limit, languages, path_prefix, min_score)
        return SearchResult(query=query, sources=self.retriever.citations(results))

    def chat(
        self, repository_id: str, question: str, limit: int, history: list[ChatTurn] | None = None,
        languages: list[str] | None = None, path_prefix: str | None = None, min_score: float = 0,
    ) -> ChatResponse:
        self._ready_index(repository_id)
        context = self._retrieve(repository_id, question, limit, languages, path_prefix, min_score)
        return ChatResponse(
            answer=self.answerer.answer(question, context, history or []), sources=self.retriever.citations(context),
        )

    def stream_chat(
        self, repository_id: str, question: str, limit: int, history: list[ChatTurn] | None = None,
        languages: list[str] | None = None, path_prefix: str | None = None, min_score: float = 0,
    ) -> Iterator[str]:
        response = self.chat(repository_id, question, limit, history, languages, path_prefix, min_score)

        def events() -> Iterator[str]:
            # Providers with only a non-streaming API are still delivered incrementally to the browser.
            for token in response.answer.split(" "):
                yield self._sse("delta", {"text": f"{token} "})
            yield self._sse("sources", {"sources": [item.model_dump() for item in response.sources]})
            yield self._sse("done", {})

        return events()

    def _index_job(
        self, repository: GitHubRepository, requested_branch: str | None, access_token: str | None, indexed_at: datetime,
    ) -> None:
        index = RepositoryIndex(
            id=repository.id, url=repository.url, owner=repository.owner, name=repository.name,
            branch=requested_branch, status="indexing", indexed_at=indexed_at, updated_at=datetime.now(UTC),
            progress=3, stage="Cloning repository", file_count=0, chunk_count=0, chunks=[],
        )
        self._save(index)
        try:
            branch = clone_repository(repository, self._repository_path(repository), requested_branch, access_token)
            index = index.model_copy(update={"branch": branch or requested_branch, "progress": 10, "stage": "Discovering supported files", "updated_at": datetime.now(UTC)})
            self._save(index)
            files = discover_source_files(
                self._repository_path(repository), self.settings.max_file_size_bytes, self.settings.max_repository_files,
            )
            if not files:
                raise ValueError("No supported, non-empty source or documentation files were found.")
            chunks = []
            total = len(files)
            progress_interval = max(1, total // 25)
            for position, source in enumerate(files, start=1):
                for chunk in chunk_source_file(source, self.settings.chunk_size, self.settings.chunk_overlap):
                    chunk.embedding = self.embeddings.embed(f"{chunk.path}\n{chunk.content}")
                    chunks.append(chunk)
                if position == total or position % progress_interval == 0:
                    progress = min(95, 10 + int(position / total * 85))
                    self._save(index.model_copy(update={
                        "progress": progress, "stage": f"Embedding files ({position}/{total})", "file_count": position,
                        "chunk_count": len(chunks), "updated_at": datetime.now(UTC),
                    }))
            ready = index.model_copy(update={
                "status": "ready", "progress": 100, "stage": "Ready", "file_count": len(files),
                "chunk_count": len(chunks), "chunks": chunks, "error": None, "updated_at": datetime.now(UTC),
            })
            self._save(ready)
        except Exception as exc:
            failed = index.model_copy(update={
                "status": "failed", "stage": "Indexing failed", "error": str(exc), "updated_at": datetime.now(UTC),
            })
            self._save(failed)
        finally:
            access_token = None

    def _retrieve(
        self, repository_id: str, query: str, limit: int, languages: list[str] | None = None,
        path_prefix: str | None = None, min_score: float = 0,
    ):
        query_embedding = self.retriever.query_embedding(query)
        candidate_limit = min(80, max(limit * 5, 20))
        with self._lock:
            matches = self.store.search(repository_id, query_embedding, candidate_limit)
        return self.retriever.rerank(matches, query, limit, languages or [], path_prefix, min_score)

    def _get_index(self, repository_id: str) -> RepositoryIndex:
        with self._lock:
            index = self.store.load(repository_id)
        if not index:
            raise RepositoryNotFoundError("The repository has not been indexed yet.")
        return index

    def _ready_index(self, repository_id: str) -> RepositoryIndex:
        index = self._get_index(repository_id)
        if index.status != "ready":
            detail = index.error or f"Repository is {index.stage or index.status.lower()} ({index.progress}%)."
            raise RepositoryBusyError(detail) if index.status in {"queued", "indexing"} else ValueError(detail)
        return index

    def _save(self, index: RepositoryIndex) -> None:
        with self._lock:
            self.store.save(index)

    def _queued_index(self, repository: GitHubRepository, branch: str | None) -> RepositoryIndex:
        now = datetime.now(UTC)
        return RepositoryIndex(
            id=repository.id, url=repository.url, owner=repository.owner, name=repository.name, branch=branch,
            status="queued", indexed_at=now, updated_at=now, progress=0, stage="Queued for indexing",
            file_count=0, chunk_count=0,
        )

    @staticmethod
    def _sse(event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload)}\n\n"

    def _repository_path(self, repository: GitHubRepository) -> Path:
        return self.settings.data_dir / "repos" / repository.id

    def _repository_path_from_id(self, repository_id: str) -> Path:
        return self.settings.data_dir / "repos" / repository_id
