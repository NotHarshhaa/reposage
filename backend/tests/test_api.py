from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import create_app
from config.settings import Settings
from embeddings.hashing import HashEmbeddingProvider
from models.schemas import Chunk, RepositoryIndex
from vectorstore.local_store import LocalVectorStore


def test_health_and_retrieval_endpoints(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, cors_origins="http://localhost:3000")
    store = LocalVectorStore(tmp_path / "indexes")
    embedder = HashEmbeddingProvider(settings.embedding_dimensions)
    chunk = Chunk(
        id="README.md:0", path="README.md", start_line=1, end_line=3, language="markdown",
        content="# Demo\n\nRun the service with `uvicorn api.main:app`.",
    )
    chunk.embedding = embedder.embed(f"{chunk.path}\n{chunk.content}")
    store.save(RepositoryIndex(
        id="acme-demo-123", url="https://github.com/acme/demo.git", owner="acme", name="demo",
        status="ready", indexed_at=datetime.now(UTC), file_count=1, chunk_count=1, chunks=[chunk],
    ))
    client = TestClient(create_app(settings))

    assert client.get("/health").json()["status"] == "ok"
    repositories = client.get("/api/repositories")
    assert repositories.status_code == 200
    assert repositories.json()[0]["id"] == "acme-demo-123"

    search = client.post("/api/search", json={"repository_id": "acme-demo-123", "query": "how do I run the service"})
    assert search.status_code == 200
    assert search.json()["sources"][0]["path"] == "README.md"

    chat = client.post("/api/chat", json={"repository_id": "acme-demo-123", "question": "How do I run it?"})
    assert chat.status_code == 200
    assert "uvicorn" in chat.json()["answer"]


def test_rejects_non_github_urls(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    response = client.post("/api/repositories", json={"url": "https://example.com/repository"})
    assert response.status_code == 422
    assert "github.com" in response.json()["detail"]
