import json
import uuid
import logging
from typing import AsyncIterator, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent import run_agent_turn
from app.services import session_service
from app.db.models.sessions import Session

logger = logging.getLogger(__name__)


async def process_chat_message(
    db: AsyncSession,
    user_id: uuid.UUID,
    message: str,
    session_id: Optional[uuid.UUID] = None,
    cancel_event=None,
    agent_id: Optional[uuid.UUID] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Process a chat message through the agentic loop and yield WebSocket events:

      {"type": "session_info",  "session_id": "...", "title": "..."}
      {"type": "tool_start",    "tool_name": "...",  "tool_input": {...}}
      {"type": "tool_end",      "tool_name": "...",  "tool_result": "..."}
      {"type": "chunk",         "content": "..."}
      {"type": "done",          "session_id": "..."}
      {"type": "error",         "error": "..."}
    """
    session: Optional[Session] = None
    session_id_str: Optional[str] = None   # cached early — safe to use after rollback
    is_new_session = False

    try:
        # 1. Get or create session
        if session_id is not None:
            session = await session_service.get_session(db, session_id, user_id)
        if session is None:
            session = await session_service.create_session(db, user_id, "New Chat")
            await db.commit()
            is_new_session = True

        # Cache as string immediately — ORM object may be expired after rollback
        session_id_str = str(session.id)

        yield {"type": "session_info", "session_id": session_id_str, "title": session.title}

        # 2. Save user message
        user_msg = await session_service.add_message(db, session.id, user_id, "user", message)
        await session_service.update_session_updated_at(db, session.id)
        await db.commit()

        # 3. Build conversation history for LLM (exclude role="tool" display rows)
        history = await session_service.get_all_conversation_history(db, session.id)
        # Re-cache in case commit expired the object
        session_id_str = str(session.id)
        llm_messages = [
            {"role": c.role, "content": c.content}
            for c in history
            if c.role in ("user", "assistant")
        ]

        # 4. Auto-generate title on first message
        if is_new_session or session.title == "New Chat":
            if len([m for m in llm_messages if m["role"] == "user"]) == 1:
                try:
                    from app.core.llm.manager import llm_manager
                    new_title = await llm_manager.generate_title(message)
                    updated = await session_service.update_session_title(db, session.id, user_id, new_title)
                    await db.commit()
                    if updated:
                        yield {"type": "session_info", "session_id": session_id_str, "title": new_title}
                except Exception as e:
                    logger.warning("Title generation failed: %s", e)

        # 5. Run agent loop — yields tool_start / tool_end / chunk events
        # 6. Resolve agent config (None falls back to default system prompt)
        agent_cfg = None
        if agent_id is not None:
            try:
                from app.services.agent_service import get_agent
                from app.core.agent.config import AgentConfig
                db_agent = await get_agent(db, agent_id)
                if db_agent is not None:
                    agent_cfg = AgentConfig.from_db(db_agent)
            except Exception as e:
                logger.warning("Failed to load agent %s, using default: %s", agent_id, e)

        # 6. Run agent loop — yields tool_start / tool_end / chunk events
        full_response = ""
        tool_inputs: Dict[str, Any] = {}   # tool_name → tool_input (paired with tool_end)
        completed_tools: list[Dict[str, Any]] = []

        async for event in run_agent_turn(
            messages=llm_messages,
            session_id=session_id_str,
            user_id=str(user_id),
            conversation_id=str(user_msg.id) if user_msg else None,
            cancel_event=cancel_event,
            agent_config=agent_cfg,
        ):
            if event["type"] == "chunk":
                full_response += event["content"]
            elif event["type"] == "tool_start":
                tool_inputs[event["tool_name"]] = event["tool_input"]
            elif event["type"] == "tool_end":
                completed_tools.append({
                    "tool_name": event["tool_name"],
                    "tool_input": tool_inputs.pop(event["tool_name"], {}),
                    "tool_result": event["tool_result"],
                    "status": "done",
                })
            yield event

        # 7. Persist tool calls then assistant response (partial if stopped)
        for tool_data in completed_tools:
            await session_service.add_message(
                db, session.id, user_id, "tool", json.dumps(tool_data)
            )
        if full_response:
            await session_service.add_message(db, session.id, user_id, "assistant", full_response)
        if completed_tools or full_response:
            await session_service.update_session_updated_at(db, session.id)
            await db.commit()

        if cancel_event and cancel_event.is_set():
            yield {"type": "stopped", "session_id": session_id_str}
        else:
            yield {"type": "done", "session_id": session_id_str}

    except Exception as e:
        logger.error("process_chat_message error: %s", e, exc_info=True)
        try:
            await db.rollback()
        except Exception:
            pass
        yield {"type": "error", "error": str(e)}
        if session_id_str:
            # Use cached string — session ORM object is expired after rollback
            yield {"type": "done", "session_id": session_id_str}
