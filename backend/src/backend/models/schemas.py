from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# chat schemas
class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None 


class AgentResponse(BaseModel):
    answer: str
    sources: list[str] = []
    has_context: bool
    conversation_id: int


# history schemas
class ConversationOut(BaseModel):
    id: int
    question: str
    answer: str
    sources: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# document schemas
class DocumentOut(BaseModel):
    id: int
    original_name: str
    chunk_count: int
    status: str
    error_message: Optional[str]
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class DocumentDeleteResponse(BaseModel):
    message: str
    document_id: int