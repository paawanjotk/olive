import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sessions import Session
from app.db.models.conversations import Conversation

logger = logging.getLogger(__name__)


async def create_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str = "New Chat",
    source: str = "web",
) -> Session:
    """Create a new chat session."""
    session = Session(
        id=uuid.uuid4(),
        user_id=user_id,
        title=title,
        source=source,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    logger.info(f"Created session {session.id} for user {user_id}")
    return session


async def get_user_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    source: str = "web",
) -> List[Session]:
    """Get sessions for a user filtered by source, ordered by updated_at descending.

    Defaults to 'web' so channel sessions (slack, telegram) are hidden from the dashboard.
    """
    result = await db.execute(
        sa.select(Session)
        .where(Session.user_id == user_id, Session.source == source)
        .order_by(Session.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
) -> Optional[Session]:
    """Get a single session by ID, optionally scoped to a user."""
    query = sa.select(Session).where(Session.id == session_id)
    if user_id is not None:
        query = query.where(Session.user_id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def update_session_title(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
) -> Optional[Session]:
    """Update the title of a session."""
    session = await get_session(db, session_id, user_id)
    if session is None:
        return None
    session.title = title
    session.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(session)
    return session


async def delete_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Delete a session (and cascade delete its conversations)."""
    session = await get_session(db, session_id, user_id)
    if session is None:
        return False
    await db.delete(session)
    await db.flush()
    logger.info(f"Deleted session {session_id}")
    return True


async def get_conversation_history(
    db: AsyncSession,
    session_id: uuid.UUID,
    limit: int = 20,
) -> List[Conversation]:
    """Get the last N messages in a session, ordered by created_at."""
    # Get the last `limit` messages, then return in chronological order
    subquery = (
        sa.select(Conversation)
        .where(Conversation.session_id == session_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .subquery()
    )
    result = await db.execute(
        sa.select(Conversation)
        .where(Conversation.session_id == subquery.c.session_id)
        .where(Conversation.id == subquery.c.id)
        .order_by(Conversation.created_at.asc())
    )
    return list(result.scalars().all())


async def get_all_conversation_history(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> List[Conversation]:
    """Return every message in the session in chronological order.

    No limit — all messages in a session are relevant context.
    """
    result = await db.execute(
        sa.select(Conversation)
        .where(Conversation.session_id == session_id)
        .order_by(Conversation.created_at.asc())
    )
    return list(result.scalars().all())


async def add_message(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    content: str,
) -> Conversation:
    """Add a message to a session's conversation."""
    conversation = Conversation(
        id=uuid.uuid4(),
        session_id=session_id,
        user_id=user_id,
        role=role,
        content=content,
    )
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    return conversation


async def update_session_updated_at(
    db: AsyncSession, session_id: uuid.UUID
) -> None:
    """Touch the session updated_at timestamp."""
    await db.execute(
        sa.update(Session)
        .where(Session.id == session_id)
        .values(updated_at=datetime.now(timezone.utc))
    )
    await db.flush()
