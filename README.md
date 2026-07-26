# 🚀 RepoSage
 
> Chat with any public GitHub repository using Retrieval-Augmented Generation (RAG).
 
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-API-green)
![LangChain](https://img.shields.io/badge/LangChain-RAG-orange)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-red)
![Next.js](https://img.shields.io/badge/Next.js-Frontend-black)
![License](https://img.shields.io/badge/License-MIT-yellow)
 
---
 
## 📖 Overview
 
RepoSage is an open-source AI application that lets developers **chat with any public GitHub repository**.
 
Instead of manually reading through hundreds of files, RepoSage clones a repository, indexes its source code and documentation, generates vector embeddings, and enables natural-language conversations about the codebase — powered by a Large Language Model (LLM).
 
Whether you're exploring an unfamiliar open-source project or onboarding to a new codebase, RepoSage helps you understand a repository in minutes instead of hours.
 
---
 
## ✨ Features
 
- 🔗 Index any public GitHub repository
- 📂 Parse source code and documentation
- 📝 Support for Markdown, source code, YAML, JSON, and config files
- ✂️ Smart, language-aware document chunking
- 🧠 Semantic vector search
- 🤖 AI-powered question answering with source citations
- ⚡ Streaming responses
- 🔍 Repository-wide search
- 🐳 Docker support
- 🌙 Modern web interface
- 🔌 REST API
- 🧩 Modular, pluggable architecture (swap LLMs, embeddings, vector stores)

---

## 🔍 What is included

- FastAPI REST API with OpenAPI docs at `http://localhost:8000/docs`
- Safe public GitHub URL validation and shallow cloning with GitPython
- Guarded discovery for code, docs, YAML/JSON, Docker, and common config files
- Line-preserving chunking and local hashed vector embeddings
- Persisted JSON vector index, repository list, semantic-style search, and grounded chat citations
- Next.js + TypeScript + Tailwind interface for indexing and chat
- Docker Compose and an API test suite

The out-of-the-box answerer is intentionally **local and extractive**: it summarizes retrieved repository snippets without an API key or transmitting source to a provider. `backend/embeddings/hashing.py` and `backend/llm/extractive.py` are isolated adapter seams for OpenAI, Gemini, Ollama, BGE, Nomic, Qdrant, Chroma, or FAISS integrations.

---

## 🚀 Quick start

### Docker (recommended)

```bash
copy .env.example .env
# Edit .env only if you need non-default limits/origins.
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

On Unix-like shells, activate the venv with `source .venv/bin/activate`.

---

## 🔍 API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | API health check |
| `GET` | `/api/repositories` | List persisted indexes |
| `POST` | `/api/repositories` | Clone and index `{ "url": "https://github.com/owner/repo" }` |
| `GET` | `/api/repositories/{id}` | Get repository index metadata |
| `POST` | `/api/search` | Search `{ "repository_id", "query", "limit" }` |
| `POST` | `/api/chat` | Ask `{ "repository_id", "question", "history", "limit" }` |

Indexing is synchronous in this MVP so the `POST /api/repositories` response is immediately ready for querying. The backend accepts only clean `https://github.com/owner/repository` URLs, rejects embedded credentials and query strings, limits individual file sizes, skips dependencies/build output, and stores clones and indexes under `backend/data` (or `REPOSAGE_DATA_DIR`).

---

## 🔍 Configuration

Copy `.env.example` to `.env`. Settings use the `REPOSAGE_` prefix, including `REPOSAGE_DATA_DIR`, `REPOSAGE_MAX_FILE_SIZE_BYTES`, `REPOSAGE_MAX_REPOSITORY_FILES`, and chunk/vector settings. Set `NEXT_PUBLIC_API_URL` when the browser should access an API at a non-default origin. It is a build-time value for the Docker web image.

---

## 🔍 Validation

```bash
cd backend && pytest -q
cd frontend && npm run typecheck && npm run build
```

---

## 📂 Project layout

```text
backend/
  api/             FastAPI application and routes
  ingestion/       GitHub validation, cloning, and file discovery
  embeddings/      Pluggable embedding adapter seam
  retrieval/       Chunking and vector retrieval
  vectorstore/     Persisted local vector-store adapter
  llm/             Grounded answerer adapter seam
  services/        Indexing and query orchestration
  tests/           API tests
frontend/
  app/             Next.js interface and styles
  components/      Indexing, chat, and citation UI
  lib/             Typed API client
docker-compose.yml
```

---

## 🔍 Current scope

This runnable initial release provides local retrieval with transparent citations. Remote generative answers, streaming, background indexing, hybrid/BM25 retrieval, reranking, GitHub authentication, and additional vector/embedding providers are deliberate extension points rather than hidden or partially configured features.

---

## 🤝🏻 Pluggable Providers
 
RepoSage uses an adapter pattern so these can be swapped via config — **default is bolded**, others are supported but may need additional setup.
 
| Category | Options |
|---|---|
| LLM | **OpenAI**, Google Gemini, Ollama (local models) |
| Embeddings | **OpenAI Embeddings**, Gemini Embeddings, BGE, Nomic |
| Vector DB | **Qdrant**, Chroma, FAISS |
 
---

## 📂 📄 Supported Languages & Files
 
**Code:** Python, JavaScript, TypeScript, Go, Java, C#, Rust, C++, Shell, Terraform
 
**Config & Docs:** Dockerfile, YAML, JSON, Markdown, README, environment files, GitHub Actions workflows, Docker Compose, Kubernetes manifests
 
---

## 🤝 Contributing
 
Contributions are welcome!
 
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Open a Pull Request
Bug reports, feature requests, and documentation improvements are always appreciated.
 
---
 
## 📜 License
 
This project is licensed under the [MIT License](LICENSE).
 
---
 
## 🌟 Why RepoSage?
 
Understanding large repositories can be overwhelming. RepoSage turns a repository into a searchable knowledge base — surfacing architecture, configuration, workflows, and implementation details through conversation instead of manual file-hunting.
 
If you find this project useful, consider giving it a ⭐ on GitHub!
