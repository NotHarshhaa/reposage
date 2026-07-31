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
    ChatResponse, ChatTurn, Conversation, ConversationMessage, ConversationSummary, FileOutline, FileWeight,
    LanguageBreakdown, MetricsResponse, MultiSearchResult, RepositoryFile, RepositoryIndex, RepositoryInsights,
    RepositoryMatches, RepositorySummary, SearchResult,
)
from retrieval.chunking import chunk_source_file
from retrieval.retriever import Retriever
from retrieval.symbols import extract_symbols
from services.conversation_store import ConversationStore, conversation_to_markdown
from vectorstore.factory import create_vector_store


class RepositoryNotFoundError(LookupError):
    pass


class RepositoryBusyError(RuntimeError):
    pass


class _IndexCancelled(Exception):
    """Internal signal raised when a caller cancels an in-flight index job."""


class RepositoryService:
    """Coordinates durable repository jobs and retrieval without a separate queue service."""

    def __init__(self, settings: Settings) -> None:
        settings.ensure_directories()
        self.settings = settings
        self.embeddings = create_embedding_provider(settings)
        self.store = create_vector_store(settings)
        self.retriever = Retriever(self.embeddings)
        self.answerer = create_answer_provider(settings)
        self.conversations = ConversationStore(settings.data_dir / "conversations")
        self._lock = threading.RLock()
        self._jobs: dict[str, Future[None]] = {}
        self._cancelled: set[str] = set()
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
            self._cancelled.discard(repository.id)
            self._jobs[repository.id] = self._executor.submit(self._index_job, repository, branch, access_token, now)
            return RepositorySummary.from_index(queued)

    def reindex_repository(self, repository_id: str, branch: str | None = None, access_token: str | None = None) -> RepositorySummary:
        index = self._get_index(repository_id)
        return self.start_indexing(index.url, branch or index.branch, access_token)

    def cancel_indexing(self, repository_id: str) -> RepositorySummary:
        """Request cancellation of a queued or running index job."""
        with self._lock:
            index = self._get_index(repository_id)
            if index.status not in {"queued", "indexing"}:
                raise ValueError(f"Repository is not indexing (current status: {index.status}).")
            job = self._jobs.get(repository_id)
            self._cancelled.add(repository_id)
            if job:
                job.cancel()
            cancelled = index.model_copy(update={
                "status": "cancelled", "stage": "Cancelled", "updated_at": datetime.now(UTC),
                "error": "Indexing was cancelled before completion.", "chunks": [],
            })
            self.store.save(cancelled)
            return RepositorySummary.from_index(cancelled)

    def delete_repository(self, repository_id: str) -> None:
        with self._lock:
            index = self._get_index(repository_id)
            job = self._jobs.get(repository_id)
            if index.status in {"queued", "indexing"} and job and not job.done():
                raise RepositoryBusyError("The repository is currently indexing. Cancel the job before deleting it.")
            self.store.delete(repository_id)
            shutil.rmtree(self.settings.data_dir / "repos" / repository_id, ignore_errors=True)
            self._jobs.pop(repository_id, None)
            self._cancelled.discard(repository_id)

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

    def insights(self, repository_id: str) -> RepositoryInsights:
        index = self._ready_index(repository_id)
        files: dict[str, FileWeight] = {}
        language_files: dict[str, set[str]] = {}
        language_chunks: dict[str, int] = {}
        total_characters = 0
        for chunk in index.chunks:
            characters = len(chunk.content)
            total_characters += characters
            weight = files.get(chunk.path)
            if weight:
                files[chunk.path] = weight.model_copy(update={
                    "chunk_count": weight.chunk_count + 1, "character_count": weight.character_count + characters,
                })
            else:
                files[chunk.path] = FileWeight(path=chunk.path, language=chunk.language, chunk_count=1, character_count=characters)
            language_files.setdefault(chunk.language, set()).add(chunk.path)
            language_chunks[chunk.language] = language_chunks.get(chunk.language, 0) + 1
        chunk_total = len(index.chunks)
        languages = sorted(
            (
                LanguageBreakdown(
                    language=language, file_count=len(paths), chunk_count=language_chunks.get(language, 0),
                    share=round(language_chunks.get(language, 0) / chunk_total * 100, 2) if chunk_total else 0,
                )
                for language, paths in language_files.items()
            ),
            key=lambda item: (item.chunk_count, item.file_count), reverse=True,
        )
        largest = sorted(files.values(), key=lambda item: item.character_count, reverse=True)[:10]
        documentation = sorted(path for path, weight in files.items() if weight.language == "markdown")[:20]
        return RepositoryInsights(
            repository_id=index.id, owner=index.owner, name=index.name, branch=index.branch,
            indexed_at=index.indexed_at, file_count=len(files) or index.file_count, chunk_count=chunk_total,
            total_characters=total_characters,
            average_chunk_characters=round(total_characters / chunk_total) if chunk_total else 0,
            languages=languages, largest_files=largest, documentation_files=documentation,
        )

    def outline(self, repository_id: str, path: str) -> FileOutline:
        source = self.read_file(repository_id, path)
        content = source.content or ""
        return FileOutline(
            path=source.path, language=source.language, line_count=len(content.splitlines()),
            symbols=extract_symbols(content, source.language),
        )

    def search_all(
        self, query: str, limit_per_repository: int, repository_ids: list[str] | None = None,
        languages: list[str] | None = None, min_score: float = 0,
    ) -> MultiSearchResult:
        requested = set(repository_ids or [])
        with self._lock:
            candidates = [index for index in self.store.list() if index.status == "ready" and (not requested or index.id in requested)]
        if requested and not candidates:
            raise RepositoryNotFoundError("None of the requested repositories are indexed and ready.")
        groups: list[RepositoryMatches] = []
        for index in candidates:
            results = self._retrieve(index.id, query, limit_per_repository, languages, None, min_score)
            if results:
                groups.append(RepositoryMatches(
                    repository_id=index.id, owner=index.owner, name=index.name,
                    sources=self.retriever.citations(results),
                ))
        groups.sort(key=lambda group: group.sources[0].score if group.sources else 0, reverse=True)
        return MultiSearchResult(query=query, repositories=groups)

    def similar_code(self, repository_id: str, path: str, line: int, limit: int) -> SearchResult:
        index = self._ready_index(repository_id)
        normalized = path.replace("\\", "/").lstrip("/")
        candidates = [chunk for chunk in index.chunks if chunk.path == normalized]
        if not candidates:
            raise RepositoryNotFoundError("That file has no indexed chunks to compare.")
        anchor = min(candidates, key=lambda chunk: abs(chunk.start_line - line))
        if not anchor.embedding:
            raise ValueError("The selected chunk has no stored embedding. Re-index the repository.")
        with self._lock:
            matches = self.store.search(repository_id, anchor.embedding, min(80, max(limit * 5, 20)))
        ranked = [
            item for item in self.retriever.rerank(matches, anchor.content[:400], limit + 1)
            if not (item.chunk.path == anchor.path and item.chunk.start_line == anchor.start_line)
        ][:limit]
        return SearchResult(query=f"{anchor.path}:{anchor.start_line}", sources=self.retriever.citations(ranked))

    def save_conversation(self, repository_id: str, messages: list[ConversationMessage], title: str | None = None) -> Conversation:
        self._get_index(repository_id)
        return self.conversations.save(repository_id, messages, title)

    def list_conversations(self, repository_id: str | None = None) -> list[ConversationSummary]:
        return [ConversationSummary.from_conversation(item) for item in self.conversations.list(repository_id)]

    def get_conversation(self, conversation_id: str) -> Conversation:
        conversation = self.conversations.load(conversation_id)
        if not conversation:
            raise RepositoryNotFoundError("The requested conversation was not found.")
        return conversation

    def export_conversation(self, conversation_id: str) -> tuple[str, str]:
        conversation = self.get_conversation(conversation_id)
        return f"reposage-{conversation.id}.md", conversation_to_markdown(conversation)

    def delete_conversation(self, conversation_id: str) -> None:
        if not self.conversations.delete(conversation_id):
            raise RepositoryNotFoundError("The requested conversation was not found.")

    def metrics(self) -> MetricsResponse:
        with self._lock:
            indexes = self.store.list()
            active = sum(1 for job in self._jobs.values() if not job.done())
        by_status: dict[str, int] = {}
        for index in indexes:
            by_status[index.status] = by_status.get(index.status, 0) + 1
        return MetricsResponse(
            repositories_total=len(indexes), repositories_by_status=by_status,
            files_indexed=sum(index.file_count for index in indexes if index.status == "ready"),
            chunks_indexed=sum(index.chunk_count for index in indexes if index.status == "ready"),
            active_index_jobs=active, conversations_saved=self.conversations.count(),
            providers={
                "llm": self.settings.llm_provider, "embeddings": self.settings.embedding_provider,
                "vector_store": self.settings.vector_store_provider,
            },
        )

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
            if self._is_cancelled(repository.id):
                raise _IndexCancelled
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
                if self._is_cancelled(repository.id):
                    raise _IndexCancelled
                for chunk in chunk_source_file(source, self.settings.chunk_size, self.settings.chunk_overlap):
                    chunk.embedding = self.embeddings.embed(f"{chunk.path}\n{chunk.content}")
                    chunks.append(chunk)
                if position == total or position % progress_interval == 0:
                    progress = min(95, 10 + int(position / total * 85))
                    self._save(index.model_copy(update={
                        "progress": progress, "stage": f"Embedding files ({position}/{total})", "file_count": position,
                        "chunk_count": len(chunks), "updated_at": datetime.now(UTC),
                    }))
            if self._is_cancelled(repository.id):
                raise _IndexCancelled
            ready = index.model_copy(update={
                "status": "ready", "progress": 100, "stage": "Ready", "file_count": len(files),
                "chunk_count": len(chunks), "chunks": chunks, "error": None, "updated_at": datetime.now(UTC),
            })
            self._save(ready)
        except _IndexCancelled:
            self._save(index.model_copy(update={
                "status": "cancelled", "stage": "Cancelled", "chunks": [], "updated_at": datetime.now(UTC),
                "error": "Indexing was cancelled before completion.",
            }))
        except Exception as exc:
            failed = index.model_copy(update={
                "status": "failed", "stage": "Indexing failed", "error": str(exc), "updated_at": datetime.now(UTC),
            })
            self._save(failed)
        finally:
            access_token = None
            with self._lock:
                self._cancelled.discard(repository.id)

    def _is_cancelled(self, repository_id: str) -> bool:
        with self._lock:
            return repository_id in self._cancelled

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
