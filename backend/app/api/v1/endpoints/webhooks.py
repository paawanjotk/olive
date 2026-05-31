"""Inbound messaging webhooks.

Telegram: every message → run_channel_turn("telegram", chat_id, text)
          /connect <code> → links the chat to the Ollive user who generated the code
"""
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if settings.TELEGRAM_WEBHOOK_SECRET:
        if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

    update = await request.json()
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return {"ok": True}

    from app.services import telegram_service

    # ── /connect <code> — link this Telegram chat to an Ollive user ────────────
    if text.startswith("/connect"):
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else ""
        if not code:
            await telegram_service.send_message(
                chat_id,
                "Usage: /connect <code>\n\nGet your code from the Ollive dashboard → Settings → Connect Telegram.",
            )
            return {"ok": True}

        await _handle_telegram_connect(chat_id, code)
        return {"ok": True}

    # ── Regular message → direct chat ─────────────────────────────────────────
    await telegram_service.send_chat_action(chat_id, "typing")

    from app.core.channel_chat import run_channel_turn
    response, _ = await run_channel_turn(
        platform="telegram",
        external_id=chat_id,
        user_text=text,
    )
    await telegram_service.send_message(chat_id, response)
    return {"ok": True}


async def _handle_telegram_connect(chat_id: str, code: str) -> None:
    """Exchange a verification code for a ChannelBinding."""
    import uuid
    import json
    from app.services import telegram_service

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL)
        try:
            raw = await r.get(f"telegram_connect:{code}")
            if not raw:
                await telegram_service.send_message(
                    chat_id,
                    "Invalid or expired code. Generate a new one from the Ollive dashboard.",
                )
                return
            data = json.loads(raw)
            user_id = uuid.UUID(data["user_id"])
            await r.delete(f"telegram_connect:{code}")
        finally:
            await r.aclose()
    except Exception as e:
        logger.exception("Redis error during Telegram connect: %s", e)
        await telegram_service.send_message(chat_id, "Connection failed — please try again.")
        return

    # Upsert the binding
    try:
        from sqlalchemy import select
        from app.db.base import get_session_factory
        from app.db.models.channels import ChannelBinding

        async with get_session_factory()() as db:
            existing = (await db.execute(
                select(ChannelBinding).where(
                    ChannelBinding.platform == "telegram",
                    ChannelBinding.external_id == chat_id,
                )
            )).scalar_one_or_none()

            if existing:
                existing.user_id = user_id
                existing.is_active = True
                existing.config = {}
            else:
                db.add(ChannelBinding(
                    user_id=user_id,
                    platform="telegram",
                    external_id=chat_id,
                    config={},
                ))
            await db.commit()
    except Exception as e:
        logger.exception("DB error during Telegram connect: %s", e)
        await telegram_service.send_message(chat_id, "Connection failed — please try again.")
        return

    await telegram_service.send_message(
        chat_id,
        "Connected! You can now chat with the Ollive agent directly here. "
        "Your conversations will also appear in the Ollive dashboard.",
    )
    logger.info("Telegram chat %s linked to user %s", chat_id, user_id)
