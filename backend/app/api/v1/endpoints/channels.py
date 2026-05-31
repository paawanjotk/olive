"""Channel API — platform-agnostic connect / status / disconnect.

Adding a new channel (WhatsApp, Discord, …):
  1. Add a connector class to app/services/channel_connector.py
  2. Register it in _CONNECTORS — done. No API changes needed.
"""
import logging
import uuid
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import get_session_factory
from app.db.models.channels import ChannelBinding
from app.dependencies.auth import get_current_user
from app.schemas.channels import (
    ChannelBindingCreate,
    ChannelBindingResponse,
    SetWebhookRequest,
)
from app.services import telegram_service
from app.services.channel_connector import get_connector, supported_platforms

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session


def _uid(current_user: dict) -> uuid.UUID:
    return uuid.UUID(current_user["id"])


# ── Unified channel connect / status / disconnect ──────────────────────────────

class ChannelConnectRequest(BaseModel):
    platform: str
    config: dict[str, Any] = {}


@router.post("/connect")
async def connect_channel(
    body: ChannelConnectRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect any supported channel. `platform` selects the connector.
    Returns platform-specific result (immediate for Slack; code+instructions for Telegram)."""
    try:
        connector = get_connector(body.platform)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = await connector.connect(_uid(current_user), db, body.config)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/status")
async def channel_status(
    platform: str = Query(..., description=f"One of: {', '.join(supported_platforms())}"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the connection status for the given platform."""
    try:
        connector = get_connector(platform)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await connector.status(_uid(current_user), db)


@router.delete("/disconnect", status_code=204)
async def disconnect_channel(
    platform: str = Query(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate the binding for the given platform."""
    try:
        connector = get_connector(platform)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await connector.disconnect(_uid(current_user), db)


# ── Manual channel bindings (workflow/agent routing) ──────────────────────────

@router.post("", response_model=ChannelBindingResponse, status_code=201)
async def create_binding(
    body: ChannelBindingCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = _uid(current_user)
    existing = (await db.execute(
        select(ChannelBinding).where(
            ChannelBinding.platform == body.platform,
            ChannelBinding.external_id == body.external_id,
        )
    )).scalar_one_or_none()
    if existing is not None:
        if existing.user_id != user_id:
            raise HTTPException(status_code=409, detail="Chat already bound by another user")
        await db.delete(existing)
        await db.flush()

    binding = ChannelBinding(
        user_id=user_id,
        platform=body.platform,
        external_id=body.external_id,
        workflow_id=body.workflow_id,
        agent_id=body.agent_id,
        config=body.config,
    )
    db.add(binding)
    await db.commit()
    await db.refresh(binding)
    return binding


@router.get("", response_model=list[ChannelBindingResponse])
async def list_bindings(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(ChannelBinding)
        .where(ChannelBinding.user_id == _uid(current_user))
        .order_by(ChannelBinding.created_at.desc())
    )).scalars().all()
    return list(rows)


@router.delete("/{binding_id}", status_code=204)
async def delete_binding(
    binding_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    binding = (await db.execute(
        select(ChannelBinding).where(
            ChannelBinding.id == binding_id,
            ChannelBinding.user_id == _uid(current_user),
        )
    )).scalar_one_or_none()
    if binding is None:
        raise HTTPException(status_code=404, detail="Binding not found")
    await db.delete(binding)
    await db.commit()


# ── Telegram webhook registration ─────────────────────────────────────────────

@router.post("/telegram/set-webhook")
async def set_telegram_webhook(
    body: SetWebhookRequest,
    current_user: dict = Depends(get_current_user),
):
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN not configured")
    return await telegram_service.set_webhook(
        body.webhook_url, secret_token=settings.TELEGRAM_WEBHOOK_SECRET or None
    )
