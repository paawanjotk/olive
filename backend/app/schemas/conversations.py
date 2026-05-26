import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel

from app.schemas.sessions import SessionResponse


class MessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationHistoryResponse(BaseModel):
    messages: List[MessageResponse]
    session: SessionResponse
