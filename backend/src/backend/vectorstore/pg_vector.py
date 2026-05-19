import logging
from functools import lru_cache
from typing import Optional

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_postgres.vectorstores import PGVector

from src.backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def _get_embeddings() -> OllamaEmbeddings:
    """Initialize Ollama embeddings model singleton."""
    logger.info("Loading Ollama embedding model: %s", settings.ollama_embedding_model)
    return OllamaEmbeddings(
        model=settings.ollama_embedding_model,
        base_url=settings.ollama_base_url,
    )


@lru_cache(maxsize=1)
def get_vectorstore() -> PGVector:
    """Get or initialize the PGVector store instance."""
    return PGVector(
        embeddings=_get_embeddings(),
        collection_name=settings.pgvector_collection,
        connection=settings.pgvector_connection_string,
        use_jsonb=True,
        create_extension=True,
    )


def add_documents(docs: list[Document]) -> int:
    """Add documents to vector store and return total processed chunk count."""
    vs = get_vectorstore()
    vs.add_documents(docs)
    logger.info("Added %d chunks to PGVector", len(docs))
    return len(docs)


def similarity_search(
    query: str,
    k: int = 6,
    min_score: Optional[float] = None,
) -> list[tuple[Document, float]]:
    """
    Query the vector store and return chunks above the similarity threshold.

    Uses similarity_search_with_relevance_scores which returns values in [0, 1]
    where 1 = perfect match. Chunks below min_score are discarded to prevent
    low-quality context from reaching the LLM.
    """
    threshold = min_score if min_score is not None else settings.min_similarity_score
    vs = get_vectorstore()

    results: list[tuple[Document, float]] = vs.similarity_search_with_relevance_scores(
        query, k=k
    )

    # Log all raw scores to make threshold tuning observable
    for doc, score in results:
        logger.info(
            "RAW score=%.4f | source=%s | content=%s",
            score,
            doc.metadata.get("source", "unknown"),
            doc.page_content[:80].replace("\n", " "),
        )

    filtered = [(doc, score) for doc, score in results if score >= threshold]

    logger.info(
        "Vector search: %d raw results, %d passed threshold (min=%.2f)",
        len(results),
        len(filtered),
        threshold,
    )

    return filtered


def delete_documents_by_source(source_filename: str) -> int:
    try:
        import psycopg
        # psycopg3 usa una connection string diferente — quita el driver
        conn_string = settings.pgvector_connection_string.replace(
            "postgresql+psycopg://", "postgresql://"
        )
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM langchain_pg_embedding
                    WHERE collection_id = (
                        SELECT uuid FROM langchain_pg_collection WHERE name = %s
                    )
                    AND cmetadata->>'source' = %s
                    """,
                    (settings.pgvector_collection, source_filename),
                )
                deleted = cur.rowcount
                conn.commit()
        logger.info("Deleted %d chunks for source file '%s'", deleted, source_filename)
        return deleted
    except Exception as exc:
        logger.error("Could not delete chunks for '%s': %s", source_filename, exc)
        return 0


def document_count() -> int:
    """Return total number of chunks currently stored in the collection."""
    try:
        import psycopg
        with psycopg.connect(settings.pgvector_connection_string) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = "
                    "(SELECT uuid FROM langchain_pg_collection WHERE name = %s)",
                    (settings.pgvector_collection,),
                )
                return cur.fetchone()[0]
    except Exception as exc:
        logger.warning("Could not fetch document chunk count: %s", exc)
        return 0