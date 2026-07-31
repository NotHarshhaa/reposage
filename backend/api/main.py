from __future__ import annotations

import hmac
import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from config.settings import Settings, get_settings
from models.schemas import (
    ChatRequest, ChatResponse, Conversation, ConversationSummary, FileOutline, HealthResponse,
    IndexRepositoryRequest, MetricsResponse, MultiSearchRequest, MultiSearchResult, ReindexRepositoryRequest,
    RepositoryFile, RepositoryInsights, RepositorySummary, SaveConversationRequest, SearchRequest, SearchResult,
    SimilarCodeRequest,
)
from services.repository_service import RepositoryBusyError, RepositoryNotFoundError, RepositoryService

logger = logging.getLogger("reposage.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    service = RepositoryService(runtime_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        recovered = service.recover_interrupted_jobs()
        if recovered:
            logger.warning("marked %d interrupted repository index job(s) as failed", recovered)
        try:
            yield
        finally:
            service.shutdown()

    app = FastAPI(
        title=runtime_settings.app_name, version="0.2.0",
        description="Retrieval-grounded chat, search, and source browsing for GitHub repositories.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=runtime_settings.allowed_origins, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"],
    )
    request_windows: dict[str, deque[float]] = defaultdict(deque)

    @app.middleware("http")
    async def safeguards(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        response: Response
        try:
            if runtime_settings.api_key and request.url.path.startswith("/api/"):
                supplied = request.headers.get("X-API-Key", "")
                if not hmac.compare_digest(supplied, runtime_settings.api_key):
                    response = JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Valid X-API-Key required."})
                    response.headers["X-Request-ID"] = request_id
                    return response
            if runtime_settings.rate_limit_requests_per_minute and request.url.path.startswith("/api/"):
                client = request.client.host if request.client else "unknown"
                now = time.monotonic()
                window = request_windows[client]
                while window and now - window[0] >= 60:
                    window.popleft()
                # Drop idle clients so the limiter's memory stays bounded over long uptimes.
                for tracked in [key for key, values in request_windows.items() if not values and key != client]:
                    request_windows.pop(tracked, None)
                if len(window) >= runtime_settings.rate_limit_requests_per_minute:
                    response = JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"detail": "Rate limit exceeded. Try again shortly."}, headers={"Retry-After": "60"},
                    )
                    response.headers["X-Request-ID"] = request_id
                    return response
                window.append(now)
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            logger.info("request_id=%s method=%s path=%s duration_ms=%.1f", request_id, request.method, request.url.path, (time.perf_counter() - started) * 1000)

    def raise_service_error(exc: Exception) -> None:
        if isinstance(exc, RepositoryNotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if isinstance(exc, RepositoryBusyError):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok", version=app.version,
            providers={"llm": runtime_settings.llm_provider, "embeddings": runtime_settings.embedding_provider, "vector_store": runtime_settings.vector_store_provider},
        )

    @app.get("/api/repositories", response_model=list[RepositorySummary], tags=["repositories"])
    def list_repositories() -> list[RepositorySummary]:
        return service.list_repositories()

    @app.post("/api/repositories", response_model=RepositorySummary, status_code=status.HTTP_202_ACCEPTED, tags=["repositories"])
    def index_repository(request: IndexRepositoryRequest) -> RepositorySummary:
        try:
            return service.start_indexing(str(request.url), request.branch, request.access_token)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    @app.get("/api/repositories/{repository_id}", response_model=RepositorySummary, tags=["repositories"])
    def get_repository(repository_id: str) -> RepositorySummary:
        try:
            return service.get_repository(repository_id)
        except Exception as exc:
            raise_service_error(exc)

    @app.post("/api/repositories/{repository_id}/reindex", response_model=RepositorySummary, status_code=status.HTTP_202_ACCEPTED, tags=["repositories"])
    def reindex_repository(repository_id: str, request: ReindexRepositoryRequest) -> RepositorySummary:
        try:
            return service.reindex_repository(repository_id, request.branch, request.access_token)
        except Exception as exc:
            raise_service_error(exc)

    @app.delete("/api/repositories/{repository_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["repositories"])
    def delete_repository(repository_id: str) -> Response:
        try:
            service.delete_repository(repository_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except Exception as exc:
            raise_service_error(exc)

    @app.get("/api/repositories/{repository_id}/files", response_model=list[RepositoryFile], tags=["repositories"])
    def list_files(repository_id: str) -> list[RepositoryFile]:
        try:
            return service.list_files(repository_id)
        except Exception as exc:
            raise_service_error(exc)

    @app.get("/api/repositories/{repository_id}/files/{file_path:path}", response_model=RepositoryFile, tags=["repositories"])
    def read_file(repository_id: str, file_path: str) -> RepositoryFile:
        try:
            return service.read_file(repository_id, file_path)
        except Exception as exc:
            raise_service_error(exc)

    @app.post("/api/search", response_model=SearchResult, tags=["retrieval"])
    def search(request: SearchRequest) -> SearchResult:
        try:
            return service.search(
                request.repository_id, request.query, request.limit, request.languages, request.path_prefix, request.min_score,
            )
        except Exception as exc:
            raise_service_error(exc)

    @app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
    def chat(request: ChatRequest) -> ChatResponse:
        try:
            return service.chat(
                request.repository_id, request.question, request.limit, request.history,
                request.languages, request.path_prefix, request.min_score,
            )
        except Exception as exc:
            raise_service_error(exc)

    @app.post("/api/chat/stream", tags=["chat"])
    def stream_chat(request: ChatRequest) -> StreamingResponse:
        try:
            events = service.stream_chat(
                request.repository_id, request.question, request.limit, request.history,
                request.languages, request.path_prefix, request.min_score,
            )
            return StreamingResponse(
                events, media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        except Exception as exc:
            raise_service_error(exc)

    @app.post("/api/repositories/{repository_id}/cancel", response_model=RepositorySummary, tags=["repositories"])
    def cancel_indexing(repository_id: str) -> RepositorySummary:
        try:
            return service.cancel_indexing(repository_id)
        except Exception as exc:
            raise_service_error(exc)

    @app.get("/api/repositories/{repository_id}/insights", response_model=RepositoryInsights, tags=["analysis"])
    def repository_insights(repository_id: str) -> RepositoryInsights:
        try:
            return service.insights(repository_id)
        except Exception as exc:
            raise_service_error(exc)

    @app.get("/api/repositories/{repository_id}/outline", response_model=FileOutline, tags=["analysis"])
    def file_outline(repository_id: str, path: str = Query(min_length=1, max_length=500)) -> FileOutline:
        try:
            return service.outline(repository_id, path)
        except Exception as exc:
            raise_service_error(exc)

    @app.post("/api/search/all", response_model=MultiSearchResult, tags=["retrieval"])
    def search_all(request: MultiSearchRequest) -> MultiSearchResult:
        try:
            return service.search_all(
                request.query, request.limit_per_repository, request.repository_ids, request.languages, request.min_score,
            )
        except Exception as exc:
            raise_service_error(exc)

    @app.post("/api/similar", response_model=SearchResult, tags=["retrieval"])
    def similar_code(request: SimilarCodeRequest) -> SearchResult:
        try:
            return service.similar_code(request.repository_id, request.path, request.line, request.limit)
        except Exception as exc:
            raise_service_error(exc)

    @app.get("/api/conversations", response_model=list[ConversationSummary], tags=["conversations"])
    def list_conversations(repository_id: str | None = Query(default=None, max_length=200)) -> list[ConversationSummary]:
        return service.list_conversations(repository_id)

    @app.post("/api/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED, tags=["conversations"])
    def save_conversation(request: SaveConversationRequest) -> Conversation:
        try:
            return service.save_conversation(request.repository_id, request.messages, request.title)
        except Exception as exc:
            raise_service_error(exc)

    @app.get("/api/conversations/{conversation_id}", response_model=Conversation, tags=["conversations"])
    def get_conversation(conversation_id: str) -> Conversation:
        try:
            return service.get_conversation(conversation_id)
        except Exception as exc:
            raise_service_error(exc)

    @app.get("/api/conversations/{conversation_id}/export", tags=["conversations"])
    def export_conversation(conversation_id: str) -> PlainTextResponse:
        try:
            filename, markdown = service.export_conversation(conversation_id)
            return PlainTextResponse(
                markdown, media_type="text/markdown; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as exc:
            raise_service_error(exc)

    @app.delete("/api/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["conversations"])
    def delete_conversation(conversation_id: str) -> Response:
        try:
            service.delete_conversation(conversation_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except Exception as exc:
            raise_service_error(exc)

    @app.get("/api/metrics", response_model=MetricsResponse, tags=["system"])
    def metrics() -> MetricsResponse:
        return service.metrics()

    return app


app = create_app()
