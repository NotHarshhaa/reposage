from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or a .env file."""

    app_name: str = "RepoSage API"
    api_prefix: str = "/api"
    data_dir: Path = Path(__file__).resolve().parents[1] / "data"
    cors_origins: str = "http://localhost:3000"
    max_file_size_bytes: int = 750_000
    max_repository_files: int = 3_000
    chunk_size: int = 1_200
    chunk_overlap: int = 160
    index_workers: int = Field(default=2, ge=1, le=8)

    # Optional perimeter controls. Empty/zero values preserve local-development behavior.
    api_key: str | None = None
    rate_limit_requests_per_minute: int = Field(default=0, ge=0, le=10_000)

    # Local providers are deliberately the defaults: no source code leaves the host.
    llm_provider: Literal["extractive", "openai", "gemini", "ollama"] = "extractive"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    gemini_api_key: str | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    ollama_base_url: str = "http://localhost:11434"
    llm_temperature: float = 0.1

    embedding_provider: Literal["hashing", "openai", "gemini", "bge", "nomic"] = "hashing"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 256
    bge_model: str = "BAAI/bge-small-en-v1.5"
    nomic_api_key: str | None = None
    nomic_base_url: str = "https://api-atlas.nomic.ai/v1"

    vector_store_provider: Literal["local", "qdrant", "chroma", "faiss"] = "local"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection_prefix: str = "reposage"
    chroma_path: Path | None = None
    faiss_path: Path | None = None

    provider_timeout_seconds: float = 60.0

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="REPOSAGE_", extra="ignore"
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_chroma_path(self) -> Path:
        return self.chroma_path or self.data_dir / "chroma"

    @property
    def resolved_faiss_path(self) -> Path:
        return self.faiss_path or self.data_dir / "faiss"

    def ensure_directories(self) -> None:
        (self.data_dir / "repos").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "indexes").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
