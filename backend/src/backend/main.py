import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.config.settings import get_settings
from src.backend.models.database import init_db
from src.backend.controllers.agent_controller import router as agent_router
from src.backend.controllers.auth_controller import router as auth_router
from src.backend.controllers.document_controller import router as document_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting F1 Agent API...")

    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    await init_db()
    logger.info("Database initialized.")

    try:
        from src.backend.vectorstore.pg_vector import get_vectorstore
        get_vectorstore()
        logger.info("Vector store initialized.")
    except Exception as exc:
        logger.warning("Could not pre-load vector store: %s", exc)

    try:
        from src.backend.agents.f1_agent import get_agent
        get_agent()
        logger.info("LangGraph agent compiled successfully.")
    except Exception as exc:
        logger.warning("Failed to compile agent: %s", exc)

    logger.info("Server running at http://0.0.0.0:8000")
    yield

    logger.info("Shutting down F1 Agent API...")


app = FastAPI(
    title="F1 Agent API",
    description=(
        "API for an intelligent Formula 1 agent built with "
        "LangChain, LangGraph, and RAG over PGVector."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,     prefix="/api/v1")
app.include_router(agent_router,    prefix="/api/v1")
app.include_router(document_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "model": settings.ollama_model,
        "embedding_model": settings.ollama_embedding_model,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "F1 Agent API",
        "docs": "/docs",
        "health": "/health",
    }