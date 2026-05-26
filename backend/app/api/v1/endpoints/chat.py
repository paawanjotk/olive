import asyncio
import json
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.base import get_session_factory
from app.services.chat_service import process_chat_message

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/chat/{client_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    client_id: str,
):
    """
    WebSocket endpoint for streaming chat.

    Client sends:
        {"type": "chat",  "message": "...", "session_id": "uuid-or-null", "user_id": "uuid"}
        {"type": "stop"}  — cancels the active generation

    Server streams back:
        {"type": "session_info", "session_id": "uuid", "title": "..."}
        {"type": "chunk",        "content": "..."}
        {"type": "done",         "session_id": "uuid"}
        {"type": "stopped",      "session_id": "uuid"}
        {"type": "error",        "error": "..."}
    """
    await websocket.accept()
    logger.info(f"WebSocket connected: client_id={client_id}")

    session_factory = get_session_factory()
    cancel_event = asyncio.Event()

    async def stream_response(
        user_id: uuid.UUID,
        session_id: Optional[uuid.UUID],
        message_text: str,
        agent_id: Optional[uuid.UUID] = None,
    ):
        async with session_factory() as db:
            try:
                async for event in process_chat_message(
                    db=db,
                    user_id=user_id,
                    message=message_text,
                    session_id=session_id,
                    cancel_event=cancel_event,
                    agent_id=agent_id,
                ):
                    try:
                        await websocket.send_text(json.dumps(event))
                    except Exception:
                        return
            except WebSocketDisconnect:
                return
            except Exception as e:
                logger.error(f"Error processing chat for client {client_id}: {e}", exc_info=True)
                try:
                    await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
                except Exception:
                    pass

    try:
        while True:
            raw_data = await websocket.receive_text()

            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError as e:
                await websocket.send_text(
                    json.dumps({"type": "error", "error": f"Invalid JSON: {e}"})
                )
                continue

            msg_type = data.get("type")

            if msg_type == "stop":
                cancel_event.set()
                continue

            if msg_type != "chat":
                await websocket.send_text(
                    json.dumps({"type": "error", "error": f"Unknown message type: {msg_type}"})
                )
                continue

            message_text = data.get("message", "").strip()
            if not message_text:
                await websocket.send_text(
                    json.dumps({"type": "error", "error": "Empty message"})
                )
                continue

            user_id_str = data.get("user_id")
            if not user_id_str:
                await websocket.send_text(
                    json.dumps({"type": "error", "error": "user_id is required"})
                )
                continue

            try:
                user_id = uuid.UUID(user_id_str)
            except ValueError:
                await websocket.send_text(
                    json.dumps({"type": "error", "error": "Invalid user_id format"})
                )
                continue

            session_id: Optional[uuid.UUID] = None
            session_id_str = data.get("session_id")
            if session_id_str:
                try:
                    session_id = uuid.UUID(session_id_str)
                except ValueError:
                    logger.warning(f"Invalid session_id format: {session_id_str}")

            agent_id: Optional[uuid.UUID] = None
            agent_id_str = data.get("agent_id")
            if agent_id_str:
                try:
                    agent_id = uuid.UUID(agent_id_str)
                except ValueError:
                    logger.warning(f"Invalid agent_id format: {agent_id_str}")

            logger.info(
                f"Processing chat message for user={user_id}, "
                f"session={session_id}, agent={agent_id}, client={client_id}"
            )

            # Reset cancel flag and start streaming as a background task so
            # we can receive a "stop" message while streaming is in progress.
            cancel_event.clear()
            asyncio.create_task(stream_response(user_id, session_id, message_text, agent_id))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: client_id={client_id}")
        cancel_event.set()
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for client {client_id}: {e}", exc_info=True)
        cancel_event.set()
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "error": "Internal server error"})
            )
        except Exception:
            pass
    finally:
        logger.info(f"WebSocket connection closed: client_id={client_id}")
