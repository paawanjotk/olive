"""Telegram Bot API client. Uses httpx directly — the Bot API is plain JSON
over HTTPS, so no extra dependency is needed.

Channel abstraction: this module is the only place that knows Telegram specifics.
Adding WhatsApp/Slack later means a sibling module with the same send_message
contract; the workflow engine stays channel-agnostic via trigger_context."""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"


def _token() -> str:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    return settings.TELEGRAM_BOT_TOKEN


async def send_message(chat_id: str | int, text: str) -> None:
    """Send a text message. Telegram caps messages at 4096 chars — chunk if longer."""
    url = _API.format(token=_token(), method="sendMessage")
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)] or ["(empty response)"]
    async with httpx.AsyncClient(timeout=15.0) as client:
        for chunk in chunks:
            resp = await client.post(url, json={"chat_id": chat_id, "text": chunk})
            if resp.status_code != 200:
                logger.warning("Telegram sendMessage failed (%s): %s", resp.status_code, resp.text)


async def send_chat_action(chat_id: str | int, action: str = "typing") -> None:
    """Show a 'typing…' indicator while the workflow runs."""
    url = _API.format(token=_token(), method="sendChatAction")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json={"chat_id": chat_id, "action": action})
    except Exception as e:
        logger.debug("sendChatAction failed: %s", e)


async def set_webhook(webhook_url: str, secret_token: str | None = None) -> dict:
    url = _API.format(token=_token(), method="setWebhook")
    payload: dict = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload)
        return resp.json()


async def delete_webhook() -> dict:
    url = _API.format(token=_token(), method="deleteWebhook")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url)
        return resp.json()
