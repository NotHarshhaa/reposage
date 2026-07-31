# 🚀 RepoSage

> Search, browse, and chat with GitHub repositories using Retrieval-Augmented Generation (RAG).

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-API-green)
![Next.js](https://img.shields.io/badge/Next.js-Frontend-black)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Overview

RepoSage shallow-clones a GitHub repository, indexes supported source and documentation files, and provides source-cited search and chat. Indexing runs in a bounded background worker with durable progress metadata, so the UI and API remain responsive while repositories are processed. The default hashing embeddings, extractive answerer, and JSON index run locally without credentials or a remote service.

## Features

- Background indexing with queued/indexing/ready/failed/cancelled status, progress, branch selection, re-indexing, cancellation, and deletion
- Public GitHub repositories plus optional private-repository clones with a per-request token that is never persisted
- Source browsing API and UI with file list, line-numbered previews, symbol outlines, cited search results, and path/language filters
- Repository insights: language mix, indexed size, average chunk size, largest files, and documentation inventory
- Hybrid semantic + lexical reranking, configurable score threshold, cross-repository search, and "find similar code" from any file
- Streaming chat over Server-Sent Events, bounded conversation history, and saved conversations with Markdown export
- Operational metrics endpoint, optional API-key protection, per-client rate limiting, request IDs, timing logs, Docker Compose, tests, and CI
- Dark mode, configurable LLM/embedding/vector-store providers, and local-first defaults that keep source code on your machine

## Quick start

### Docker

```bash
copy .env.example .env
docker compose up --build
```

Open `http://localhost:3000`. The API is at `http://localhost:8000`, and interactive docs are at `/docs`.

### Local development

Requires Python 3.11+, Node.js 18+ (Node 20 recommended), and Git.

```bash
# terminal 1
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.main:app --reload

# terminal 2
cd frontend
npm install
npm run dev
```

On Unix-like shells, activate the Python environment with `source .venv/bin/activate`.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Health, version, and selected provider metadata |
| `GET` | `/api/metrics` | Repository counts by status, indexed totals, active jobs, saved conversations |
| `GET` | `/api/repositories` | List repository indexes and background-job status |
| `POST` | `/api/repositories` | Queue `{ "url", "branch?", "access_token?" }` for indexing; returns `202` |
| `GET` | `/api/repositories/{id}` | Inspect status, progress, counts, and errors |
| `POST` | `/api/repositories/{id}/reindex` | Queue a new index of an existing repository; returns `202` |
| `POST` | `/api/repositories/{id}/cancel` | Cancel a queued or running index job |
| `DELETE` | `/api/repositories/{id}` | Delete the local clone and vector index |
| `GET` | `/api/repositories/{id}/files` | List source files available to browse |
| `GET` | `/api/repositories/{id}/files/{path}` | Read one indexed source file |
| `GET` | `/api/repositories/{id}/outline?path=` | Symbol outline (classes, functions, types, headings) for one file |
| `GET` | `/api/repositories/{id}/insights` | Language mix, indexed size, largest files, documentation inventory |
| `POST` | `/api/search` | Filtered search: `{ "repository_id", "query", "languages?", "path_prefix?", "min_score?" }` |
| `POST` | `/api/search/all` | Search every ready repository: `{ "query", "repository_ids?", "limit_per_repository?" }` |
| `POST` | `/api/similar` | Related chunks for `{ "repository_id", "path", "line?" }` |
| `POST` | `/api/chat` | Non-streaming answer with `{ "repository_id", "question", "history?" }` |
| `POST` | `/api/chat/stream` | Same request as chat, delivered as SSE `delta`, `sources`, and `done` events |
| `GET` | `/api/conversations` | List saved conversations, optionally filtered by `repository_id` |
| `POST` | `/api/conversations` | Save `{ "repository_id", "messages", "title?" }`; returns `201` |
| `GET` | `/api/conversations/{id}` | Read one saved conversation with its cited sources |
| `GET` | `/api/conversations/{id}/export` | Download the conversation as Markdown |
| `DELETE` | `/api/conversations/{id}` | Delete a saved conversation |

Search and chat only accept repositories in `ready` state. Poll the repository detail endpoint (or use the UI) until `progress` reaches 100. Cancelling sets status `cancelled` and discards partial vectors, so the repository can be re-indexed cleanly. Saved conversations are stored as JSON under the backend data directory. A private-repository access token is sent only to Git during that clone: it is never written to the repository URL, Git config, application manifests, or logs. Supply it again for a private re-index.

Symbol outlines use line-anchored patterns rather than per-language parsers: repository code is never executed, and unsupported languages return an empty outline instead of failing.

## Configuration and safeguards

Copy `.env.example` to `.env`. All configuration keys are prefixed with `REPOSAGE_` for the backend.

```dotenv
# Background indexing and optional perimeter controls
REPOSAGE_INDEX_WORKERS=2
REPOSAGE_API_KEY=
REPOSAGE_RATE_LIMIT_REQUESTS_PER_MINUTE=0

# If REPOSAGE_API_KEY is set, send this header to every /api request:
# X-API-Key: <your value>
# For the included browser client, set NEXT_PUBLIC_REPOSAGE_API_KEY to the same
# value only for a trusted/private deployment. Never expose a production secret
# through a publicly served frontend.
```

`REPOSAGE_API_KEY` is disabled when empty. `REPOSAGE_RATE_LIMIT_REQUESTS_PER_MINUTE=0` disables the in-process limiter; set a positive value for single-instance deployments. For multi-instance or internet-facing deployments, use a gateway/WAF and shared rate-limit store as well. API responses include `X-Request-ID`, and the API logs method, path, duration, and request ID (never access tokens). On startup, any index left `queued` or `indexing` by a previous process is marked `failed` so it can be re-indexed instead of appearing stuck.

### Provider selection

| Category | Providers | Default |
|---|---|---|
| LLM | Extractive, OpenAI, Google Gemini, Ollama | Extractive |
| Embeddings | Hashing, OpenAI, Gemini, BGE, Nomic | Hashing |
| Vector store | Local JSON, Qdrant, persistent Chroma, FAISS | Local JSON |

```dotenv
# Example: hosted OpenAI plus Qdrant
REPOSAGE_LLM_PROVIDER=openai
REPOSAGE_LLM_MODEL=gpt-4o-mini
REPOSAGE_EMBEDDING_PROVIDER=openai
REPOSAGE_EMBEDDING_MODEL=text-embedding-3-small
REPOSAGE_OPENAI_API_KEY=replace-me
REPOSAGE_VECTOR_STORE_PROVIDER=qdrant
REPOSAGE_QDRANT_URL=https://your-cluster.example.cloud.qdrant.io
REPOSAGE_QDRANT_API_KEY=replace-me
```

Remote LLM and embedding selections send retrieved repository chunks to that provider. Qdrant stores chunk text and vectors at its configured endpoint. Keep the default providers, BGE, Chroma, or FAISS for a local-only deployment. Re-index after changing embedding or vector-store providers.

## Validation

```bash
cd backend && pytest -q
cd frontend && npm run typecheck && npm run build
```

GitHub Actions runs these backend and frontend checks for pushes and pull requests.

## Project layout

```text
backend/
  api/             FastAPI application and routes
  config/          Environment-backed provider and safeguard settings
  ingestion/       GitHub cloning and safe source discovery
  retrieval/       Chunking, hybrid reranking, symbol outlines, and citations
  services/        Background index jobs, query orchestration, conversation store
  vectorstore/     Local JSON, Qdrant, Chroma, and FAISS adapters
  tests/           API and provider tests
frontend/
  app/             Next.js interface and styles
  components/      Repository, chat, search, insights, and source-browser UI
  lib/             Typed API client and SSE parser
.github/workflows/ CI validation
```

## Supported files

**Code:** Python, JavaScript, TypeScript, Go, Java, C#, Rust, C++, Shell, Terraform

**Config & docs:** Dockerfile, YAML, JSON, Markdown, README, environment files, GitHub Actions workflows, Docker Compose, and Kubernetes manifests.

## License

This project is licensed under the [MIT License](LICENSE).
