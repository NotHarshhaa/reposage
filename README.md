# 🚀 RepoSage

> Chat with any public GitHub repository using Retrieval-Augmented Generation (RAG).

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-API-green)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-red)
![Next.js](https://img.shields.io/badge/Next.js-Frontend-black)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 📖 Overview

RepoSage clones a public GitHub repository, indexes source and documentation, and provides source-cited search and chat. Its LLM, embedding, and vector-store providers are configured through environment variables, so it can run entirely locally or use hosted services.

## ✨ Features

- Index public GitHub repositories with safe URL validation and shallow cloning
- Parse code, Markdown, JSON, YAML, Docker, and common configuration files
- Language-aware chunking, semantic search, and source citations
- Configurable LLM, embedding, and vector-store providers
- Local-first defaults requiring neither credentials nor a remote service
- FastAPI REST API, Next.js interface, Docker Compose, and automated tests

## 🚀 Quick start

### Docker

```bash
copy .env.example .env
# Keep the local defaults, or select providers in .env.
docker compose up --build
```

Open `http://localhost:3000`. The API is available at `http://localhost:8000`, with interactive docs at `/docs`.

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

## 🔍 API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | API health check |
| `GET` | `/api/repositories` | List persisted indexes |
| `POST` | `/api/repositories` | Clone and index `{ "url": "https://github.com/owner/repo" }` |
| `GET` | `/api/repositories/{id}` | Get repository index metadata |
| `POST` | `/api/search` | Search `{ "repository_id", "query", "limit" }` |
| `POST` | `/api/chat` | Ask `{ "repository_id", "question", "history", "limit" }` |

Indexing is synchronous in this release: a successful `POST /api/repositories` response is immediately queryable. The backend accepts clean `https://github.com/owner/repository` URLs, rejects embedded credentials and query strings, limits file sizes, and skips dependencies and build output.

## 🤝🏻 Pluggable providers

All providers are implemented and selected with `REPOSAGE_` environment variables. The **bold** entries are the default local configuration.

| Category | Providers | Notes |
|---|---|---|
| LLM | **Extractive**, OpenAI, Google Gemini, Ollama | Extractive answers from retrieved snippets without an API key. |
| Embeddings | **Hashing**, OpenAI Embeddings, Gemini Embeddings, BGE, Nomic | BGE is local through `sentence-transformers`; its model downloads on first use. |
| Vector store | **Local JSON**, Qdrant, persistent Chroma, FAISS | Qdrant supports a server or Qdrant Cloud; Chroma and FAISS persist under the data directory by default. |

Remote LLM and embedding selections send retrieved repository chunks to that provider. Qdrant also stores chunk text and vectors at the configured Qdrant endpoint. Keep the default providers, BGE, Chroma, or FAISS for a local-only deployment.

### Configuration

Copy `.env.example` to `.env`. Docker Compose passes all documented provider settings into the API container. For local backend development, export the variables in your shell or place the relevant settings in `backend/.env`.

Provider model variables are shared per category, so always set the model appropriate for the selected provider:

```dotenv
# OpenAI LLM + embeddings + Qdrant
REPOSAGE_LLM_PROVIDER=openai
REPOSAGE_LLM_MODEL=gpt-4o-mini
REPOSAGE_EMBEDDING_PROVIDER=openai
REPOSAGE_EMBEDDING_MODEL=text-embedding-3-small
REPOSAGE_OPENAI_API_KEY=replace-me
REPOSAGE_VECTOR_STORE_PROVIDER=qdrant
REPOSAGE_QDRANT_URL=https://your-cluster.example.cloud.qdrant.io
REPOSAGE_QDRANT_API_KEY=replace-me
```

```dotenv
# Gemini LLM + embeddings + persistent local Chroma
REPOSAGE_LLM_PROVIDER=gemini
REPOSAGE_LLM_MODEL=gemini-2.0-flash
REPOSAGE_EMBEDDING_PROVIDER=gemini
REPOSAGE_EMBEDDING_MODEL=text-embedding-004
REPOSAGE_GEMINI_API_KEY=replace-me
REPOSAGE_VECTOR_STORE_PROVIDER=chroma
```

```dotenv
# Fully local Ollama LLM + BGE embeddings + FAISS
REPOSAGE_LLM_PROVIDER=ollama
REPOSAGE_LLM_MODEL=llama3.2
REPOSAGE_OLLAMA_BASE_URL=http://localhost:11434
REPOSAGE_EMBEDDING_PROVIDER=bge
REPOSAGE_BGE_MODEL=BAAI/bge-small-en-v1.5
REPOSAGE_VECTOR_STORE_PROVIDER=faiss
```

For Docker Desktop, Ollama normally uses `REPOSAGE_OLLAMA_BASE_URL=http://host.docker.internal:11434`. See `.env.example` for every setting, including custom provider endpoints, request timeout, Qdrant collection prefix, and Chroma/FAISS persistence paths.

> **Re-index after changing embedding or vector-store providers.** Existing vectors may use a different model or dimension and are not portable between providers.

## 🔍 Validation

```bash
cd backend && pytest -q
cd frontend && npm run typecheck && npm run build
```

## 📂 Project layout

```text
backend/
  api/             FastAPI application and routes
  config/          Environment-backed provider settings
  embeddings/      Hashing, OpenAI, Gemini, BGE, and Nomic adapters
  retrieval/       Chunking and result/citation handling
  vectorstore/     Local JSON, Qdrant, Chroma, and FAISS adapters
  llm/             Extractive, OpenAI, Gemini, and Ollama adapters
  services/        Indexing and query orchestration
  tests/           API and provider tests
frontend/
  app/             Next.js interface and styles
  components/      shadcn/ui and HugeIcons interface components
  lib/             Typed API client
docker-compose.yml
```

## 📂 📄 Supported languages & files

**Code:** Python, JavaScript, TypeScript, Go, Java, C#, Rust, C++, Shell, Terraform

**Config & docs:** Dockerfile, YAML, JSON, Markdown, README, environment files, GitHub Actions workflows, Docker Compose, and Kubernetes manifests.

## 🤝 Contributing

Contributions are welcome: fork the repository, create a feature branch, commit your changes, and open a pull request.

## 📜 License

This project is licensed under the [MIT License](LICENSE).
