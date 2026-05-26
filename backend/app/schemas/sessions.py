import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class SessionCreate(BaseModel):
    user_id: uuid.UUID
    title: Optional[str] = "New Chat"


class SessionUpdate(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]
