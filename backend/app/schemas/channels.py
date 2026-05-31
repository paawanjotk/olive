from uuid import UUID
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, model_validator


class ChannelBindingCreate(BaseModel):
    platform: str = "telegram"
    external_id: str  # e.g. Telegram chat_id
    workflow_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    config: dict[str, Any] = {}

    @model_validator(mode="after")
    def _one_target(self):
        if not self.workflow_id and not self.agent_id:
            raise ValueError("Provide a workflow_id or agent_id to bind the channel to")
        return self


class ChannelBindingResponse(BaseModel):
    id: UUID
    user_id: UUID
    platform: str
    external_id: str
    workflow_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    config: dict[str, Any]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SetWebhookRequest(BaseModel):
    webhook_url: str
