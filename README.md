# F1 Agent

An intelligent Formula 1 web application built with **FastAPI**, **LangChain**, **LangGraph**, **RAG over PGVector**, and **React**. Authenticated users can chat with an AI agent that answers F1 questions based on uploaded documents, with built-in anti-hallucination measures.

---

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Setup & Running](#setup--running)
- [Environment Variables](#environment-variables)
- [Keycloak Setup](#keycloak-setup)
- [Uploading Documents](#uploading-documents)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Key Dependencies](#key-dependencies)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (port 5173)                   │
│              React + Vite + Tailwind CSS                 │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP + Bearer token
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 FastAPI Backend (port 8000)              │
│   /api/v1/auth/*   /api/v1/agent/*   /api/v1/documents/ │
└──────┬─────────────────┬──────────────────┬─────────────┘
       │                 │                  │
       ▼                 ▼                  ▼
┌─────────────┐  ┌──────────────┐  ┌──────────────────┐
│  Keycloak   │  │  LangGraph   │  │ Ingestion Service │
│ (port 8080) │  │  F1 Agent    │  │ (chunk + embed)   │
└─────────────┘  └──────┬───────┘  └────────┬─────────┘
                         │                   │
                         ▼                   ▼
                ┌─────────────────────────────────┐
                │    PostgreSQL + pgvector         │
                │  (vectors + conversation log)   │
                └────────────────┬────────────────┘
                                 │
                         ┌───────▼───────┐
                         │    Ollama     │
                         │  (port 11434) │
                         │  qwen2.5:7b   │
                         │  nomic-embed  │
                         └───────────────┘
```

### Agent flow (LangGraph)

```
receive_question → rephrase_question → validate_intent → retrieve_context → generate_answer
                                              │
                                         (off-topic)
                                              ↓
                                       reject_question
```

**Anti-hallucination measures:**
1. Minimum similarity threshold on vector search (`MIN_SIMILARITY_SCORE`): low-score chunks never reach the LLM.
2. The answer prompt forces explicit quote extraction before responding (chain-of-thought).
3. Post-generation validation: long answers with no topical overlap with the retrieved context are rejected.

---

## Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Python | 3.12 | Backend runtime |
| Poetry | 2.x | Python dependency manager |
| Node.js | 18+ | Frontend runtime |
| Docker + Docker Compose | 20.x / 2.x | Runs Postgres, Keycloak, and Ollama |

> **No local Ollama installation required.** Ollama runs inside Docker and pulls models automatically on first boot.

---

## Setup & Running

### 1. Clone the repository

```bash
git clone <repo-url>
cd final_implementacion
```

### 2. Start all infrastructure services

```bash
docker compose up -d
```

This starts three containers:
- **rag-postgres** — PostgreSQL with pgvector (port 5432)
- **f1-keycloak** — Keycloak identity provider (port 8080)
- **f1-ollama** — Ollama LLM server (port 11434)

On first boot, Ollama automatically pulls `qwen2.5:7b` (~4.4 GB) and `nomic-embed-text`. This takes a few minutes. Monitor progress with:

```bash
docker compose logs -f ollama
# Wait until you see "success" for both models
```

Verify all containers are running:

```bash
docker compose ps
```

### 3. Start the backend

```bash
cd backend
poetry install
poetry run uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at **http://localhost:8000**

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The app will be available at **http://localhost:5173**

Opening the URL will immediately redirect you to the Keycloak login page.

---

## Environment Variables

The `backend/.env` file is included and pre-configured for local development:

```env
# App
APP_NAME="F1 Agent"
DEBUG=false

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# PGVector
PGVECTOR_CONNECTION_STRING=postgresql+psycopg://postgres:postgres@localhost:5432/vectordb
PGVECTOR_COLLECTION=f1_knowledge

# Document ingestion
UPLOAD_DIR=../docs
CHUNK_SIZE=512
CHUNK_OVERLAP=100
MIN_SIMILARITY_SCORE=0.55

# Keycloak
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=f1-realm
KEYCLOAK_CLIENT_ID=f1-frontend
```

---

## Keycloak Setup

Keycloak auto-imports the `f1-realm` configuration on first boot from `keycloak/f1-realm-realm.json`. No manual setup required.

**Pre-configured test user:**
- Username: `f1user`
- Password: `f1password`

New users can also self-register from the Keycloak login page.

**Admin console:** http://localhost:8080/admin (admin / admin)

---

## Uploading Documents

The agent only answers questions based on uploaded documents. A sample F1 facts file is included at `docs/f1_facts.txt`.

To upload it:
1. Log in at http://localhost:5173
2. Click **Documents** in the navbar
3. Drag and drop `docs/f1_facts.txt` or any F1-related PDF

Supported formats: PDF, TXT, MD, CSV, DOCX — max 50 MB per file.

---

## API Reference

All endpoints require a valid Keycloak Bearer token: `Authorization: Bearer <token>`

### Auth — `/api/v1/auth`

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/auth/me` | Returns the authenticated user's info |

### Agent — `/api/v1/agent`

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/agent/ask` | Submit a question to the F1 agent |
| `GET` | `/api/v1/agent/history` | Get conversation history (scoped to user) |
| `DELETE` | `/api/v1/agent/history/{id}` | Delete a conversation |

### Documents — `/api/v1/documents`

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/documents/upload` | Upload a document to the knowledge base |
| `GET` | `/api/v1/documents/` | List documents (scoped to user) |
| `DELETE` | `/api/v1/documents/{id}` | Delete a document and its vectors |
| `GET` | `/api/v1/documents/stats` | Get vector store stats |

Interactive API docs (Swagger UI): **http://localhost:8000/docs**

---

## Project Structure

```
final_implementacion/
├── compose.yml                        # Docker Compose: Postgres, Keycloak, Ollama
├── ollama-entrypoint.sh               # Auto-pulls Ollama models on first boot
├── .env.example                       # Environment variable reference
├── docs/
│   └── f1_facts.txt                   # Sample F1 knowledge base document
├── keycloak/
│   └── f1-realm-realm.json            # Keycloak realm auto-import config
├── backend/
│   ├── .env                           # Local environment variables
│   ├── pyproject.toml                 # Python dependencies (Poetry)
│   └── src/backend/
│       ├── main.py                    # FastAPI app entrypoint
│       ├── deps.py                    # JWT auth dependency (Keycloak JWKS)
│       ├── config/
│       │   └── settings.py            # Pydantic settings from .env
│       ├── controllers/
│       │   ├── auth_controller.py     # GET /auth/me
│       │   ├── agent_controller.py    # /agent/* routes
│       │   └── document_controller.py # /documents/* routes
│       ├── agents/
│       │   └── f1_agent.py            # LangGraph agent graph
│       ├── services/
│       │   └── ingestion_service.py   # File parsing and chunking pipeline
│       ├── vectorstore/
│       │   └── pg_vector.py           # langchain-postgres wrapper
│       └── models/
│           ├── database.py            # SQLAlchemy models + async session
│           └── schemas.py             # Pydantic request/response schemas
└── frontend/
    ├── package.json
    └── src/
        ├── main.tsx                   # Keycloak init + React bootstrap
        ├── App.tsx                    # Router + layout
        ├── keycloak.ts                # Keycloak singleton
        ├── api/
        │   └── client.ts              # Axios instance with auth interceptor
        ├── components/
        │   └── Navbar.tsx             # Navigation + logout
        └── pages/
            ├── Chat.tsx               # Chatbot interface + history sidebar
            └── Documents.tsx          # Document upload and management
```

---

## Key Dependencies

### Backend

| Library | Purpose |
|---|---|
| `fastapi` | Web framework and Swagger generation |
| `uvicorn` | ASGI server |
| `langchain` + `langgraph` | RAG agent orchestration |
| `langchain-ollama` | Local LLM integration |
| `langchain-postgres` | Vector store on PostgreSQL + pgvector |
| `langchain-text-splitters` | Document chunking |
| `python-jose[cryptography]` | Keycloak JWT validation |
| `httpx` | Fetching Keycloak JWKS |
| `pypdf` / `docx` | Text extraction |
| `pydantic-settings` | Config from `.env` |
| `asyncpg` / `psycopg` | Async PostgreSQL drivers |

### Frontend

| Library | Purpose |
|---|---|
| `react` + `vite` | UI framework and build tool |
| `tailwindcss` | Styling |
| `keycloak-js` | Keycloak authentication |
| `react-router-dom` | Client-side routing |
| `axios` | HTTP client with auth interceptors |

---

## Troubleshooting

**Blank page / HTTPS required on Keycloak login:**
The realm must have `sslRequired: none`. If the realm was imported before this setting was added, run `docker compose down -v && docker compose up -d` to force a fresh import.

**Agent replies "I don't have information about that":**
No documents are in the knowledge base. Upload files via the Documents page first.

**Ollama models not downloaded yet:**
Check progress with `docker compose logs -f ollama`. Wait for "success" to appear before using the agent.

**Cannot connect to PostgreSQL:**
Run `docker compose ps` — the `rag-postgres` container must be healthy.

**Backend 401 on valid token:**
Keycloak JWKS fetch failed. Verify `KEYCLOAK_URL` in `backend/.env` matches the running Keycloak container and that `http://localhost:8080/realms/f1-realm` responds.

**CORS errors in browser:**
Backend CORS is set to `http://localhost:5173`. Ensure the frontend runs on that exact port (`npm run dev` uses 5173 by default).
