"""Slack Web API client using httpx. Mirrors telegram_service.py contract.

Channel abstraction: only this module knows Slack specifics.
Socket-mode listener is in app/worker/slack_worker.py.

Required bot OAuth scopes:
  app_mentions:read   — receive @mentions (Events API)
  chat:write          — post replies
  channels:history    — read replies in public channels (conversations.replies)
  groups:history      — read replies in private channels
  users:read          — resolve user IDs to display names (optional, for nicer summaries)
After adding scopes you MUST reinstall the app to the workspace.
"""
import logging
import re

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)
_API = "https://slack.com/api/{method}"

# Small in-process cache so we don't call users.info for every message.
_user_name_cache: dict[str, str] = {}


def _token() -> str:
    if not settings.SLACK_BOT_TOKEN:
        raise RuntimeError("SLACK_BOT_TOKEN is not configured")
    return settings.SLACK_BOT_TOKEN


def _headers() -> dict:
    return {"Authorization": f"Bearer {_token()}"}


async def send_message(channel_id: str, text: str, thread_ts: str | None = None) -> None:
    """Post a message to a Slack channel, optionally in a thread."""
    url = _API.format(method="chat.postMessage")
    chunks = [text[i:i + 3000] for i in range(0, len(text), 3000)] or ["(empty response)"]
    async with httpx.AsyncClient(timeout=15.0) as client:
        for chunk in chunks:
            payload: dict = {"channel": channel_id, "text": chunk, "mrkdwn": True}
            if thread_ts:
                payload["thread_ts"] = thread_ts
            resp = await client.post(url, json=payload, headers=_headers())
            data = resp.json()
            if not data.get("ok"):
                logger.warning("Slack chat.postMessage failed: %s", data.get("error"))


async def send_blocks(channel_id: str, blocks: list, thread_ts: str | None = None) -> None:
    """Send a Block Kit message to a Slack channel."""
    if not settings.SLACK_BOT_TOKEN:
        return
    payload: dict = {"channel": channel_id, "blocks": blocks}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers=_headers(),
            json=payload,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Slack send_blocks error: %s", data.get("error"))


async def update_message(channel_id: str, ts: str, text: str = "", blocks: list | None = None) -> None:
    """Update (replace) an existing Slack message."""
    if not settings.SLACK_BOT_TOKEN:
        return
    payload: dict = {"channel": channel_id, "ts": ts}
    if text:
        payload["text"] = text
    if blocks is not None:
        payload["blocks"] = blocks
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://slack.com/api/chat.update",
            headers=_headers(),
            json=payload,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Slack update_message error: %s", data.get("error"))


async def get_thread_messages(channel_id: str, thread_ts: str) -> list[dict]:
    """Fetch every message in a Slack thread (parent + replies) for context.

    Logs the exact Slack error on failure — the most common is `missing_scope`,
    which means the bot lacks channels:history / groups:history."""
    url = _API.format(method="conversations.replies")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            url,
            params={"channel": channel_id, "ts": thread_ts, "limit": 100},
            headers=_headers(),
        )
        data = resp.json()
    if not data.get("ok"):
        err = data.get("error")
        logger.error(
            "Slack conversations.replies failed: %s (channel=%s ts=%s). "
            "If 'missing_scope', add channels:history + groups:history to the bot "
            "and reinstall the app.", err, channel_id, thread_ts,
        )
        return []
    msgs = data.get("messages", [])
    logger.info("Fetched %d Slack thread message(s) from channel %s", len(msgs), channel_id)
    return msgs


async def get_user_name(user_id: str) -> str:
    """Resolve a Slack user id to a display name (cached). Falls back to the id."""
    if not user_id or user_id == "unknown":
        return "unknown"
    if user_id in _user_name_cache:
        return _user_name_cache[user_id]
    url = _API.format(method="users.info")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"user": user_id}, headers=_headers())
        data = resp.json()
        if data.get("ok"):
            u = data.get("user", {})
            prof = u.get("profile", {})
            name = (prof.get("display_name") or prof.get("real_name")
                    or u.get("real_name") or u.get("name") or user_id)
            _user_name_cache[user_id] = name
            return name
        logger.debug("users.info failed for %s: %s", user_id, data.get("error"))
    except Exception as e:
        logger.debug("users.info error for %s: %s", user_id, e)
    return user_id


def strip_mentions(text: str) -> str:
    """Remove Slack mention tokens like <@U123ABC> from text."""
    return re.sub(r"<@[A-Z0-9]+>", "", text or "").strip()


async def format_thread_for_prompt(messages: list[dict]) -> str:
    """Render thread messages as 'Name: message' lines, resolving user names and
    stripping raw mention tokens so the LLM reads clean conversational text."""
    lines = []
    for m in messages:
        if m.get("subtype") == "bot_message" and not m.get("user"):
            continue
        uid = m.get("user") or m.get("username") or "unknown"
        name = await get_user_name(uid)
        text = strip_mentions(m.get("text", ""))
        if text:
            lines.append(f"{name}: {text}")
    return "\n".join(lines)
