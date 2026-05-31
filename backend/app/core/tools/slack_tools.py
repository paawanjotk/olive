"""Slack memory fetch tools.

Agents use these to read Slack channel history and thread content without
having the full workspace loaded into their session context. Each call is
scoped — list threads in a channel, or read one specific thread — so an
agent can explore Slack in a distributed way.

Required bot OAuth scopes: channels:history, groups:history, users:read.
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_API = "https://slack.com/api/{method}"


def _headers() -> dict:
    from app.core.config import settings
    if not settings.SLACK_BOT_TOKEN:
        raise RuntimeError("SLACK_BOT_TOKEN is not configured")
    return {"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"}


async def slack_list_threads(
    channel_id: str,
    limit: int = 20,
    oldest: Optional[str] = None,
    latest: Optional[str] = None,
) -> str:
    """Fetch parent messages (thread starters) from a Slack channel.

    Returns a formatted summary of each thread's opening message so the agent
    can decide which threads to read in full via slack_get_thread.
    """
    params: dict = {"channel": channel_id, "limit": min(limit, 100)}
    if oldest:
        params["oldest"] = oldest
    if latest:
        params["latest"] = latest

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            _API.format(method="conversations.history"),
            params=params,
            headers=_headers(),
        )
    data = resp.json()
    if not data.get("ok"):
        err = data.get("error", "unknown")
        logger.error("slack_list_threads failed for channel %s: %s", channel_id, err)
        return f"Error fetching threads: {err}"

    messages = data.get("messages", [])
    if not messages:
        return "No messages found in this channel for the specified range."

    lines = [f"Channel {channel_id} — {len(messages)} parent message(s):\n"]
    for m in messages:
        ts = m.get("ts", "")
        text = (m.get("text") or "").strip()[:200]
        reply_count = m.get("reply_count", 0)
        thread_indicator = f" [{reply_count} replies]" if reply_count else ""
        lines.append(f"  ts={ts}{thread_indicator}: {text}")

    return "\n".join(lines)


async def slack_get_thread(channel_id: str, thread_ts: str) -> str:
    """Fetch all messages in a specific Slack thread (parent + replies).

    Returns formatted conversation text. Use the ts values from
    slack_list_threads to identify which thread to read.
    """
    from app.services.slack_service import get_thread_messages, format_thread_for_prompt

    messages = await get_thread_messages(channel_id, thread_ts)
    if not messages:
        return f"No messages found in thread {thread_ts} of channel {channel_id}."

    formatted = await format_thread_for_prompt(messages)
    header = f"Thread {thread_ts} in channel {channel_id} ({len(messages)} message(s)):\n"
    return header + formatted
