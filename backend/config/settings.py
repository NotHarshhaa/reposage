from functools import lru_cache
from pathlib import Path

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
    embedding_dimensions: int = 256

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="REPOSAGE_", extra="ignore"
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def ensure_directories(self) -> None:
        (self.data_dir / "repos").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "indexes").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
