from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from config.settings import Settings, get_settings
from models.schemas import (
    ChatRequest, ChatResponse, HealthResponse, IndexRepositoryRequest,
    RepositorySummary, SearchRequest, SearchResult,
)
from services.repository_service import RepositoryNotFoundError, RepositoryService


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    service = RepositoryService(runtime_settings)
    app = FastAPI(title=runtime_settings.app_name, version="0.1.0", description="Retrieval-grounded chat for public GitHub repositories.")
    app.add_middleware(
        CORSMiddleware, allow_origins=runtime_settings.allowed_origins, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )

    def raise_service_error(exc: Exception) -> None:
        if isinstance(exc, RepositoryNotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=app.version)

    @app.get("/api/repositories", response_model=list[RepositorySummary], tags=["repositories"])
    def list_repositories() -> list[RepositorySummary]:
        return service.list_repositories()

    @app.post("/api/repositories", response_model=RepositorySummary, tags=["repositories"])
    def index_repository(request: IndexRepositoryRequest) -> RepositorySummary:
        try:
            return service.index_repository(str(request.url))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    @app.get("/api/repositories/{repository_id}", response_model=RepositorySummary, tags=["repositories"])
    def get_repository(repository_id: str) -> RepositorySummary:
        try:
            return service.get_repository(repository_id)
        except Exception as exc:
            raise_service_error(exc)

    @app.post("/api/search", response_model=SearchResult, tags=["retrieval"])
    def search(request: SearchRequest) -> SearchResult:
        try:
            return service.search(request.repository_id, request.query, request.limit)
        except Exception as exc:
            raise_service_error(exc)

    @app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
    def chat(request: ChatRequest) -> ChatResponse:
        try:
            return service.chat(request.repository_id, request.question, request.limit)
        except Exception as exc:
            raise_service_error(exc)

    return app


app = create_app()
