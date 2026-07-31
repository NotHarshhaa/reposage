from datetime import UTC, datetime
from pathlib import Path
from time import sleep

from fastapi.testclient import TestClient

from api.main import create_app
from config.settings import Settings
from embeddings.hashing import HashEmbeddingProvider
from ingestion.loader import SourceFile
from models.schemas import Chunk, RepositoryIndex
from vectorstore.local_store import LocalVectorStore


def seed_index(tmp_path: Path) -> str:
    settings = Settings(data_dir=tmp_path, cors_origins="http://localhost:3000")
    store = LocalVectorStore(tmp_path / "indexes")
    embedder = HashEmbeddingProvider(settings.embedding_dimensions)
    repository_id = "acme-demo-123"
    chunks = [
        Chunk(id="README.md:0", path="README.md", start_line=1, end_line=3, language="markdown", content="# Demo\n\nRun the service with `uvicorn api.main:app`."),
        Chunk(id="src/app.py:0", path="src/app.py", start_line=1, end_line=2, language="python", content="def run():\n    return 'ready'"),
    ]
    for chunk in chunks:
        chunk.embedding = embedder.embed(f"{chunk.path}\n{chunk.content}")
    store.save(RepositoryIndex(
        id=repository_id, url="https://github.com/acme/demo.git", owner="acme", name="demo",
        status="ready", indexed_at=datetime.now(UTC), updated_at=datetime.now(UTC), progress=100,
        stage="Ready", file_count=2, chunk_count=2, chunks=chunks,
    ))
    root = tmp_path / "repos" / repository_id / "src"
    root.mkdir(parents=True)
    (tmp_path / "repos" / repository_id / "README.md").write_text(chunks[0].content, encoding="utf-8")
    (root / "app.py").write_text(chunks[1].content, encoding="utf-8")
    return repository_id


def test_health_retrieval_file_and_stream_endpoints(tmp_path: Path) -> None:
    repository_id = seed_index(tmp_path)
    client = TestClient(create_app(Settings(data_dir=tmp_path, cors_origins="http://localhost:3000")))

    health = client.get("/health")
    assert health.json()["status"] == "ok"
    assert health.json()["providers"]["llm"] == "extractive"
    assert health.headers["X-Request-ID"]

    repositories = client.get("/api/repositories")
    assert repositories.status_code == 200
    assert repositories.json()[0]["id"] == repository_id
    assert repositories.json()[0]["progress"] == 100

    search = client.post("/api/search", json={"repository_id": repository_id, "query": "how do I run the service", "languages": ["markdown"]})
    assert search.status_code == 200
    assert search.json()["sources"][0]["path"] == "README.md"

    files = client.get(f"/api/repositories/{repository_id}/files")
    assert {item["path"] for item in files.json()} == {"README.md", "src/app.py"}
    file_response = client.get(f"/api/repositories/{repository_id}/files/src/app.py")
    assert "def run" in file_response.json()["content"]
    assert client.get(f"/api/repositories/{repository_id}/files/../README.md").status_code == 404

    with client.stream("POST", "/api/chat/stream", json={"repository_id": repository_id, "question": "How do I run it?"}) as stream:
        body = "".join(stream.iter_text())
    assert stream.status_code == 200
    assert "event: delta" in body
    assert "event: sources" in body


def test_background_indexing_lifecycle(tmp_path: Path, monkeypatch) -> None:
    import services.repository_service as repository_service

    def fake_clone(repository, target, branch=None, access_token=None):
        target.mkdir(parents=True, exist_ok=True)
        return branch or "main"

    monkeypatch.setattr(repository_service, "clone_repository", fake_clone)
    monkeypatch.setattr(repository_service, "discover_source_files", lambda *_: [
        SourceFile(path="README.md", content="# Demo\nRun it with uvicorn.", language="markdown"),
    ])
    client = TestClient(create_app(Settings(data_dir=tmp_path, index_workers=1)))
    queued = client.post("/api/repositories", json={"url": "https://github.com/acme/demo", "branch": "main"})
    assert queued.status_code == 202
    assert queued.json()["status"] in {"queued", "indexing", "ready"}
    repository_id = queued.json()["id"]

    for _ in range(100):
        detail = client.get(f"/api/repositories/{repository_id}").json()
        if detail["status"] == "ready":
            break
        sleep(0.01)
    assert detail["status"] == "ready"
    assert detail["progress"] == 100
    assert detail["branch"] == "main"

    reindex = client.post(f"/api/repositories/{repository_id}/reindex", json={})
    assert reindex.status_code == 202
    for _ in range(100):
        detail = client.get(f"/api/repositories/{repository_id}").json()
        if detail["status"] == "ready":
            break
        sleep(0.01)
    deleted = client.delete(f"/api/repositories/{repository_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/repositories/{repository_id}").status_code == 404


def test_optional_api_key_and_rate_limit(tmp_path: Path) -> None:
    protected = TestClient(create_app(Settings(data_dir=tmp_path / "protected", api_key="test-key")))
    unauthorized = protected.get("/api/repositories")
    assert unauthorized.status_code == 401
    assert unauthorized.headers["X-Request-ID"]
    assert protected.get("/api/repositories", headers={"X-API-Key": "test-key"}).status_code == 200

    limited = TestClient(create_app(Settings(data_dir=tmp_path / "limited", rate_limit_requests_per_minute=1)))
    assert limited.get("/api/repositories").status_code == 200
    assert limited.get("/api/repositories").status_code == 429


def test_interrupted_jobs_are_recovered_on_startup(tmp_path: Path) -> None:
    store = LocalVectorStore(tmp_path / "indexes")
    store.save(RepositoryIndex(
        id="acme-stale-123", url="https://github.com/acme/stale.git", owner="acme", name="stale",
        status="indexing", indexed_at=datetime.now(UTC), updated_at=datetime.now(UTC), progress=42,
        stage="Embedding files (4/9)", file_count=4, chunk_count=4, chunks=[],
    ))
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        detail = client.get("/api/repositories/acme-stale-123").json()
    assert detail["status"] == "failed"
    assert "interrupted" in detail["error"].lower()


def test_rejects_non_github_urls(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    response = client.post("/api/repositories", json={"url": "https://example.com/repository"})
    assert response.status_code == 422
    assert "github.com" in response.json()["detail"]
