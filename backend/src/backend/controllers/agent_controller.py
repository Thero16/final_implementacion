import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.models.database import Conversation, get_db
from src.backend.models.schemas import QuestionRequest, AgentResponse, ConversationOut
from src.backend.agents.f1_agent import run_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["F1 Agent"])


@router.post("/ask", response_model=AgentResponse)
async def ask(
    payload: QuestionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a question to the F1 agent."""
    if not payload.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    logger.info("Question received: %s", payload.question)

    result = run_agent(
        question=payload.question,
        session_id=payload.session_id or "default",
    )

    conv = Conversation(
        question=payload.question,
        answer=result["answer"],
        sources=json.dumps(result["sources"]),
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    return AgentResponse(
        answer=result["answer"],
        sources=result["sources"],
        has_context=result["has_context"],
        conversation_id=conv.id,
    )


@router.get("/history", response_model=list[ConversationOut])
async def get_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Fetch recent conversation history."""
    result = await db.execute(
        select(Conversation)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
    )
    convs = result.scalars().all()

    output = []
    for c in convs:
        try:
            sources = json.loads(c.sources) if c.sources else []
        except (json.JSONDecodeError, TypeError):
            sources = []
        output.append(
            ConversationOut(
                id=c.id,
                question=c.question,
                answer=c.answer,
                sources=sources,
                created_at=c.created_at,
            )
        )
    return output


@router.delete("/history/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific record from history."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    await db.execute(
        delete(Conversation).where(Conversation.id == conversation_id)
    )
    await db.commit()
    return {"message": "Conversation deleted.", "id": conversation_id}