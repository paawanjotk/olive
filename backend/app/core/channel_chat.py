"""Unified channel chat handler — used by Slack, Telegram, and any future channel.

Flow for every inbound message:
  1. Resolve ChannelBinding(platform, external_id) → owner user_id
  2. Find-or-create a Session (session_id stored in binding.config["session_id"])
  3. Load Conversation history from DB (same as web chat)
  4. Run run_agent_turn → collect full response
  5. Persist user + assistant messages to DB (session appears in dashboard)

Two public entry-points:
  run_channel_turn()           — collect everything, return final string (Telegram)
  run_channel_turn_streaming() — async-generator yielding (event, accumulated_text)
                                 so the caller can react to tool_start mid-flight (Slack)

Adding a new channel: one thin adapter that calls one of these. No changes here.
"""
import logging
import uuid
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)


# ── Shared context setup ───────────────────────────────────────────────────────

async def _resolve_context(platform: str, external_id: str, user_text: str):
    """Returns (db, messages, agent_config, user_id, session_id) or raises."""
    from sqlalchemy import select
    from app.db.base import get_session_factory
    from app.db.models.channels import ChannelBinding
    from app.services import session_service
    from app.core.agent.config import AgentConfig
    from app.core.tools.registry import set_tool_user_id

    db_factory = get_session_factory()
    db = db_factory()
    await db.__aenter__()

    binding = (await db.execute(
        select(ChannelBinding).where(
            ChannelBinding.platform == platform,
            ChannelBinding.external_id == external_id,
            ChannelBinding.is_active.is_(True),
        )
    )).scalar_one_or_none()

    if binding is None:
        await db.__aexit__(None, None, None)
        return None  # caller sends "not connected" message

    user_id: uuid.UUID = binding.user_id

    # Find-or-create session (id stored in binding.config so it survives restarts)
    config: dict = dict(binding.config or {})
    session_id_str: Optional[str] = config.get("session_id")
    session = None

    if session_id_str:
        try:
            session = await session_service.get_session(db, uuid.UUID(session_id_str), user_id)
        except Exception:
            session = None

    if session is None:
        session = await session_service.create_session(
            db, user_id,
            title=f"{platform.title()} · {external_id}",
        )
        config["session_id"] = str(session.id)
        binding.config = config
        await db.commit()
        await db.refresh(session)

    session_id: uuid.UUID = session.id

    # Load DB conversation history
    history = await session_service.get_all_conversation_history(db, session_id)
    messages: list[dict] = [
        {"role": conv.role, "content": conv.content}
        for conv in history
        if conv.role in ("user", "assistant")
    ]
    messages.append({"role": "user", "content": user_text})

    # Resolve agent config (binding can optionally pin a specific agent)
    agent_config = AgentConfig.default()
    if binding.agent_id:
        from app.db.models.agents import Agent
        agent = (await db.execute(
            select(Agent).where(Agent.id == binding.agent_id, Agent.is_active.is_(True))
        )).scalar_one_or_none()
        if agent:
            agent_config = AgentConfig.from_db(agent)

    set_tool_user_id(str(user_id))
    return db, messages, agent_config, user_id, session_id


_NOT_CONNECTED = (
    "This chat isn't connected to an Ollive account yet. "
    "Open the Ollive dashboard → Settings → connect this channel."
)


# ── Public: fire-and-forget (Telegram, or any channel that doesn't need live updates) ──

async def run_channel_turn(
    platform: str,
    external_id: str,
    user_text: str,
) -> tuple[str, Optional[uuid.UUID]]:
    """Run one agent turn and return (response_text, user_id)."""
    from app.core.agent.loop import run_agent_turn
    from app.services import session_service

    ctx = await _resolve_context(platform, external_id, user_text)
    if ctx is None:
        return _NOT_CONNECTED, None

    db, messages, agent_config, user_id, session_id = ctx
    chunks: list[str] = []

    try:
        async for ev in run_agent_turn(
            messages,
            user_id=str(user_id),
            session_id=str(session_id),
            agent_config=agent_config,
        ):
            if ev.get("type") == "chunk":
                chunks.append(ev["content"])
    except Exception as e:
        logger.exception("Agent turn failed for %s:%s", platform, external_id)
        await db.__aexit__(None, None, None)
        return f"Sorry, something went wrong: {e}", user_id

    response = "".join(chunks).strip() or "(no response)"
    await _persist(db, session_id, user_id, user_text, response)
    await db.__aexit__(None, None, None)
    return response, user_id


# ── Public: streaming (Slack — updates placeholder as tool calls happen) ──────

async def run_channel_turn_streaming(
    platform: str,
    external_id: str,
    user_text: str,
) -> AsyncIterator[tuple[dict, str]]:
    """Async-generator that yields (agent_event, accumulated_response_so_far).

    Callers react to "tool_start" events to update a status message, then read
    the final accumulated response after the generator is exhausted.
    """
    from app.core.agent.loop import run_agent_turn
    from app.services import session_service

    ctx = await _resolve_context(platform, external_id, user_text)
    if ctx is None:
        yield {"type": "error", "content": _NOT_CONNECTED}, _NOT_CONNECTED
        return

    db, messages, agent_config, user_id, session_id = ctx
    chunks: list[str] = []

    try:
        async for ev in run_agent_turn(
            messages,
            user_id=str(user_id),
            session_id=str(session_id),
            agent_config=agent_config,
        ):
            if ev.get("type") == "chunk":
                chunks.append(ev["content"])
            accumulated = "".join(chunks)
            yield ev, accumulated
    except Exception as e:
        logger.exception("Agent turn failed for %s:%s", platform, external_id)
        error_msg = f"Sorry, something went wrong: {e}"
        yield {"type": "error", "content": error_msg}, error_msg
        await db.__aexit__(None, None, None)
        return

    response = "".join(chunks).strip() or "(no response)"
    await _persist(db, session_id, user_id, user_text, response)
    await db.__aexit__(None, None, None)


async def _persist(db, session_id, user_id, user_text, response):
    from app.services import session_service
    try:
        await session_service.add_message(db, session_id, user_id, "user", user_text)
        await session_service.add_message(db, session_id, user_id, "assistant", response)
        await session_service.update_session_updated_at(db, session_id)
        await db.commit()
    except Exception as e:
        logger.warning("Could not persist channel messages: %s", e)
