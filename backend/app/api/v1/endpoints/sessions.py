import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.schemas.sessions import (
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    SessionListResponse,
)
from app.schemas.conversations import ConversationHistoryResponse, MessageResponse
from app.services import session_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/user/{user_id}", response_model=SessionListResponse)
async def list_user_sessions(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all sessions for a user, ordered by most recently updated."""
    sessions = await session_service.get_user_sessions(db, user_id)
    return SessionListResponse(sessions=sessions)


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_in: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session."""
    title = session_in.title or "New Chat"
    session = await session_service.create_session(db, session_in.user_id, title)
    await db.commit()
    return session


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    session_update: SessionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a session's title."""
    session = await session_service.get_session(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    updated = await session_service.update_session_title(
        db, session_id, session.user_id, session_update.title
    )
    await db.commit()
    return updated


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a session and all its conversations."""
    session = await session_service.get_session(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    deleted = await session_service.delete_session(db, session_id, session.user_id)
    await db.commit()

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )


@router.get("/{session_id}/messages", response_model=ConversationHistoryResponse)
async def get_session_messages(
    session_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get all messages in a session."""
    session = await session_service.get_session(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    conversations = await session_service.get_all_conversation_history(
        db, session_id
    )

    messages = [
        MessageResponse(
            id=conv.id,
            session_id=conv.session_id,
            role=conv.role,
            content=conv.content,
            created_at=conv.created_at,
        )
        for conv in conversations
    ]

    return ConversationHistoryResponse(messages=messages, session=session)
