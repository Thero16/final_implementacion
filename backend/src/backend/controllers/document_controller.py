import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.models.database import Document, get_db
from src.backend.models.schemas import DocumentOut, DocumentDeleteResponse
from src.backend.services.ingestion_service import (
    ingest_file,
    delete_file_from_disk,
    generate_saved_filename,
    SUPPORTED_EXTENSIONS,
)
from src.backend.vectorstore.pg_vector import delete_documents_by_source

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])

MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a file to extend the F1 agent's knowledge base.
    Supported formats: PDF, TXT, MD, CSV, DOCX.
    """
    original_name = file.filename or "unnamed"
    ext = Path(original_name).suffix.lower()
    
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Format '{ext}' not supported. Allowed: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size limit of {MAX_FILE_SIZE_MB} MB.",
        )
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    saved_filename = generate_saved_filename(original_name)
    doc_record = Document(
        filename=saved_filename,
        original_name=original_name,
        status="processing",
    )
    db.add(doc_record)
    await db.commit()
    await db.refresh(doc_record)

    # Ingestion pipeline
    try:
        chunk_count = ingest_file(file_bytes, original_name, saved_filename)
        doc_record.status = "ready"
        doc_record.chunk_count = chunk_count
        logger.info("Processed '%s': %d chunks created", original_name, chunk_count)
    except ValueError as exc:
        doc_record.status = "error"
        doc_record.error_message = str(exc)
        logger.error("Error processing '%s': %s", original_name, exc)
    except Exception as exc:
        doc_record.status = "error"
        doc_record.error_message = f"Internal error: {exc}"
        logger.exception("Unexpected failure processing '%s'", original_name)

    await db.commit()
    await db.refresh(doc_record)

    if doc_record.status == "error":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=doc_record.error_message,
        )

    return doc_record


@router.get("/", response_model=list[DocumentOut])
async def list_documents(
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded documents."""
    result = await db.execute(
        select(Document).order_by(Document.uploaded_at.desc())
    )
    return result.scalars().all()


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and clean its vectors from PGVector."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    deleted_chunks = delete_documents_by_source(doc.filename)
    logger.info("Deleted %d chunks from PGVector for '%s'", deleted_chunks, doc.original_name)

    delete_file_from_disk(doc.filename)

    await db.execute(delete(Document).where(Document.id == document_id))
    await db.commit()

    return DocumentDeleteResponse(
        message=f"Document '{doc.original_name}' successfully deleted ({deleted_chunks} chunks).",
        document_id=document_id,
    )


@router.get("/stats")
async def documents_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get document and vector store stats."""
    from src.backend.vectorstore.pg_vector import document_count

    result = await db.execute(
        select(Document).where(Document.status == "ready")
    )
    docs = result.scalars().all()
    total_chunks = sum(d.chunk_count for d in docs)

    return {
        "total_documents": len(docs),
        "total_chunks": total_chunks,
        "total_vectors_in_store": document_count(),
    }