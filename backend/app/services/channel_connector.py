"""Platform-agnostic channel connector service.

Adding a new channel = implement one class with connect/status/disconnect,
register it in CONNECTORS. No API changes needed.

connect() contract:
  - For one-shot auth (Slack): returns {"connected": True, ...details}
  - For code-exchange auth (Telegram): returns {"pending": True, "code": ..., ...instructions}
  - After code exchange completes (Telegram webhook): binding is written, status() returns connected
"""
import logging
import random
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.channels import ChannelBinding

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _upsert_binding(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    platform: str,
    external_id: str,
    config: dict,
) -> ChannelBinding:
    existing = (await db.execute(
        select(ChannelBinding).where(
            ChannelBinding.platform == platform,
            ChannelBinding.external_id == external_id,
        )
    )).scalar_one_or_none()

    if existing:
        existing.user_id = user_id
        existing.is_active = True
        existing.config = {**dict(existing.config or {}), **config}
    else:
        existing = ChannelBinding(
            user_id=user_id, platform=platform,
            external_id=external_id, config=config,
        )
        db.add(existing)

    await db.commit()
    await db.refresh(existing)
    return existing


async def _get_binding(
    db: AsyncSession, *, user_id: uuid.UUID, platform: str
) -> ChannelBinding | None:
    return (await db.execute(
        select(ChannelBinding).where(
            ChannelBinding.platform == platform,
            ChannelBinding.user_id == user_id,
            ChannelBinding.is_active.is_(True),
        )
    )).scalar_one_or_none()


async def _deactivate_binding(
    db: AsyncSession, *, user_id: uuid.UUID, platform: str
) -> None:
    binding = (await db.execute(
        select(ChannelBinding).where(
            ChannelBinding.platform == platform,
            ChannelBinding.user_id == user_id,
        )
    )).scalar_one_or_none()
    if binding:
        binding.is_active = False
        await db.commit()


# ── Slack ──────────────────────────────────────────────────────────────────────

class SlackConnector:
    """Single-step: calls auth.test with the installed bot token → links workspace."""

    async def connect(
        self, user_id: uuid.UUID, db: AsyncSession, config: dict
    ) -> dict[str, Any]:
        if not settings.SLACK_BOT_TOKEN:
            return {"error": "SLACK_BOT_TOKEN not configured"}

        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"},
            )
        data = resp.json()
        if not data.get("ok"):
            return {"error": f"Slack auth.test failed: {data.get('error')}"}

        team_id: str = data["team_id"]
        workspace_name: str = data.get("team", "Slack Workspace")

        await _upsert_binding(
            db, user_id=user_id, platform="slack", external_id=team_id,
            config={"workspace_name": workspace_name},
        )
        logger.info("Slack workspace %s (%s) linked to user %s", workspace_name, team_id, user_id)
        return {"connected": True, "workspace_name": workspace_name, "team_id": team_id}

    async def status(self, user_id: uuid.UUID, db: AsyncSession) -> dict[str, Any]:
        binding = await _get_binding(db, user_id=user_id, platform="slack")
        if not binding:
            return {"connected": False}
        cfg = dict(binding.config or {})
        return {
            "connected": True,
            "workspace_name": cfg.get("workspace_name", "Slack Workspace"),
            "team_id": binding.external_id,
        }

    async def disconnect(self, user_id: uuid.UUID, db: AsyncSession) -> None:
        await _deactivate_binding(db, user_id=user_id, platform="slack")


# ── Telegram ───────────────────────────────────────────────────────────────────

class TelegramConnector:
    """Two-step: generate a short-lived code → user sends /connect <code> to bot."""

    async def connect(
        self, user_id: uuid.UUID, db: AsyncSession, config: dict
    ) -> dict[str, Any]:
        if not settings.TELEGRAM_BOT_TOKEN:
            return {"error": "TELEGRAM_BOT_TOKEN not configured"}

        import json
        import redis.asyncio as aioredis

        code = f"{random.randint(0, 999999):06d}"
        r = aioredis.from_url(settings.REDIS_URL)
        try:
            await r.setex(
                f"telegram_connect:{code}", 600,
                json.dumps({"user_id": str(user_id)}),
            )
        finally:
            await r.aclose()

        bot_username = await self._bot_username()
        return {
            "pending": True,
            "code": code,
            "bot_username": bot_username,
            "expires_in_seconds": 600,
            "instruction": f"Open Telegram, message {bot_username}, and send: /connect {code}",
        }

    async def status(self, user_id: uuid.UUID, db: AsyncSession) -> dict[str, Any]:
        binding = await _get_binding(db, user_id=user_id, platform="telegram")
        if not binding:
            return {"connected": False}
        return {"connected": True, "chat_id": binding.external_id}

    async def disconnect(self, user_id: uuid.UUID, db: AsyncSession) -> None:
        await _deactivate_binding(db, user_id=user_id, platform="telegram")

    async def _bot_username(self) -> str:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
                )
            me = resp.json().get("result", {})
            if me.get("username"):
                return f"@{me['username']}"
        except Exception:
            pass
        return "@YourBot"


# ── Registry ───────────────────────────────────────────────────────────────────

_CONNECTORS: dict[str, Any] = {
    "slack": SlackConnector(),
    "telegram": TelegramConnector(),
    # "whatsapp": WhatsAppConnector(),  ← add here, zero other changes needed
}


def get_connector(platform: str) -> Any:
    conn = _CONNECTORS.get(platform.lower())
    if conn is None:
        supported = list(_CONNECTORS)
        raise ValueError(f"Unknown platform '{platform}'. Supported: {supported}")
    return conn


def supported_platforms() -> list[str]:
    return list(_CONNECTORS)
