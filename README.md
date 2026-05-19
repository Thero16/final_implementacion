# F1 Agent API

An intelligent Formula 1 API built with **FastAPI**, **LangChain**, **LangGraph**, and **RAG over PGVector**. The agent answers F1-related questions based on user-uploaded documents, with built-in anti-hallucination measures.

---

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Setup & Running](#setup--running)
- [Accessing Swagger](#accessing-swagger)
- [Main Endpoints](#main-endpoints)
- [Project Structure](#project-structure)
- [Key Dependencies](#key-dependencies)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌──────────────┐     HTTP      ┌───────────────────────────────┐
│    Client    │ ────────────► │       FastAPI (port 8000)      │
└──────────────┘               └──────────────┬────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                          │
             ┌──────▼──────┐        ┌─────────▼──────┐       ┌─────────▼──────┐
             │  /agent/*   │        │  /documents/*  │       │   /health      │
             │ AgentRouter │        │  DocRouter     │       │   /            │
             └──────┬──────┘        └─────────┬──────┘       └────────────────┘
                    │                         │
             ┌──────▼──────┐        ┌─────────▼──────┐
             │  LangGraph  │        │IngestionService │
             │  F1 Agent   │        │(chunking/embed) │
             └──────┬──────┘        └─────────┬──────┘
                    │                         │
             ┌──────▼─────────────────────────▼──────┐
             │        PostgreSQL + pgvector           │
             │        (embeddings + conversation log) │
             └───────────────────────────────────────┘
                    │
             ┌──────▼──────┐
             │   Ollama    │
             │ (LLM + embed)│
             └─────────────┘
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
| Python | 3.12 | Required by the project |
| Poetry | 2.x | Dependency manager |
| Docker + Docker Compose | 20.x / 2.x | Used to run PostgreSQL + pgvector |
| Ollama | Latest | Must be running before starting the API |

### Required Ollama models

> **You must install both models before running the project.** The API will not work without them.

```bash
ollama pull qwen2.5:7b        # main LLM — required for reasoning and answering
ollama pull nomic-embed-text  # embedding model — required for vector search
```

After pulling, make sure Ollama is running on `localhost:11434`:

```bash
ollama serve
# Ollama is now listening at http://localhost:11434
```

---

## Environment Variables

Create or edit `backend/.env` with the following values:

```env
# App
APP_NAME="F1 Agent"
DEBUG=false

# Ollama — URL where Ollama is running
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# PGVector — PostgreSQL connection string
PGVECTOR_CONNECTION_STRING=postgresql+psycopg://postgres:postgres@localhost:5432/vectordb
PGVECTOR_COLLECTION=f1_knowledge

# Document ingestion
UPLOAD_DIR=../docs       # directory where uploaded files are stored
CHUNK_SIZE=512
CHUNK_OVERLAP=100
MIN_SIMILARITY_SCORE=0.55
```

> **Important:** Ollama must be installed and running locally on port `11434` before starting the API. If it is not running, the agent will fail to initialize.

---

## Setup & Running

### 1. Clone the repository

```bash
git clone <repo-url>
cd final_implementacion
```

### 2. Start PostgreSQL with pgvector

```bash
docker compose up -d
```

This spins up a PostgreSQL container with the pgvector extension enabled, accessible at `localhost:5432`.

Verify it is healthy:

```bash
docker compose ps
# The rag-postgres container should show as "healthy"
```

### 3. Install backend dependencies

```bash
cd backend
poetry install
```

### 4. Configure environment variables

```bash
# A .env file is already included — edit it if you need to adjust any values:
nano .env
```

### 5. Start the server

```bash
# From the backend/ directory:
poetry run uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will be available at: **http://localhost:8000**

On startup, the server automatically:
- Initializes the PostgreSQL tables.
- Connects to the PGVector store.
- Compiles the LangGraph agent graph.

---

## Accessing Swagger

Once the server is running, open the interactive API documentation in your browser:

| Interface | URL |
|---|---|
| **Swagger UI** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |
| **Health check** | http://localhost:8000/health |

Swagger UI lets you try every endpoint directly in the browser with no additional HTTP client needed.

---

## Main Endpoints

### 🏎️ F1 Agent — `/api/v1/agent`

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/agent/ask` | Submit a question to the F1 agent |
| `GET` | `/api/v1/agent/history` | Retrieve recent conversation history (last 50) |
| `DELETE` | `/api/v1/agent/history/{id}` | Delete a specific conversation by ID |

**Example — Ask the agent:**

```bash
curl -X POST http://localhost:8000/api/v1/agent/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many championships did Ayrton Senna win?", "session_id": "my-session"}'
```

Response:
```json
{
  "answer": "Ayrton Senna won 3 Formula 1 World Championships...",
  "sources": ["f1_document.pdf"],
  "has_context": true,
  "conversation_id": 1
}
```

### 📄 Documents — `/api/v1/documents`

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/documents/upload` | Upload a document to the knowledge base |
| `GET` | `/api/v1/documents/` | List all uploaded documents |
| `DELETE` | `/api/v1/documents/{id}` | Delete a document and its vectors |
| `GET` | `/api/v1/documents/stats` | Get vector store statistics |

**Supported formats:** PDF, TXT, MD, CSV, DOCX — maximum 50 MB per file.

**Example — Upload a PDF:**

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@my_f1_document.pdf"
```

---

## Project Structure

```
final_implementacion/
├── compose.yml                   # Docker Compose: PostgreSQL + pgvector
├── docs/                         # Pre-loaded documents (PDFs, etc.)
└── backend/
    ├── .env                      # Environment variables
    ├── pyproject.toml            # Dependencies (Poetry)
    └── src/backend/
        ├── main.py               # FastAPI entrypoint
        ├── config/
        │   └── settings.py       # Configuration via pydantic-settings
        ├── controllers/
        │   ├── agent_controller.py     # Routes for /agent/*
        │   └── document_controller.py  # Routes for /documents/*
        ├── agents/
        │   └── f1_agent.py       # LangGraph agent graph
        ├── services/
        │   └── ingestion_service.py   # File parsing and chunking pipeline
        ├── vectorstore/
        │   └── pg_vector.py      # langchain-postgres wrapper
        └── models/
            ├── database.py       # SQLAlchemy models + async session
            └── schemas.py        # Pydantic request/response schemas
```

---

## Key Dependencies

| Library | Purpose |
|---|---|
| `fastapi` | Web framework and automatic Swagger generation |
| `uvicorn` | ASGI server |
| `langchain` + `langgraph` | RAG agent orchestration |
| `langchain-ollama` | Integration with local Ollama models |
| `langchain-postgres` | Vector store on top of PostgreSQL + pgvector |
| `langchain-text-splitters` | Document chunking |
| `pypdf` / `docx` | Text extraction from PDFs and DOCX files |
| `pydantic-settings` | Configuration loading from `.env` |
| `asyncpg` / `psycopg` | Async PostgreSQL drivers |
| `python-multipart` | File upload support |

---

## Troubleshooting

**Agent not responding / Ollama connection error:**
Make sure Ollama is running (`ollama serve`) and that `OLLAMA_BASE_URL` in `.env` is reachable from where the backend is running.

**Cannot connect to PostgreSQL:**
Confirm the Docker container is healthy: `docker compose ps`. The connection string in `.env` must point to `localhost:5432`.

**Agent replies "I don't have information about that":**
The agent only answers based on uploaded documents. Upload relevant files via `POST /api/v1/documents/upload` before asking questions.

**Low-score chunks not appearing in answers:**
Lower `MIN_SIMILARITY_SCORE` in `.env` (e.g. `0.4`) for broader results, or raise it for stricter precision.