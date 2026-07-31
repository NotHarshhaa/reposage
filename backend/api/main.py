from __future__ import annotations

import hmac
import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from config.settings import Settings, get_settings
from models.schemas import (
    ChatRequest, ChatResponse, HealthResponse, IndexRepositoryRequest, ReindexRepositoryRequest,
    RepositoryFile, RepositorySummary, SearchRequest, SearchResult,
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

    return app


app = create_app()
