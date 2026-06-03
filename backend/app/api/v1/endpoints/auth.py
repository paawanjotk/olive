import uuid
import logging

import sqlalchemy as sa
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models.users import User
from app.dependencies.auth import get_current_user
from app.schemas.users import UserResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/sync", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def sync_user(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the frontend after login. Upserts the Supabase user into our DB.
    Uses the JWT sub (Supabase UUID) as the canonical user ID so the same UUID
    is used everywhere — no email-based lookup needed.
    """
    user_id = uuid.UUID(current_user["id"])
    email = current_user["email"]
    name = current_user["name"] or email.split("@")[0]

    result = await db.execute(sa.select(User).where(User.id == user_id))
    existing = result.scalar_one_or_none()

    if not existing:
        # Fallback: email exists under a different (stale) UUID — Supabase re-issue
        result = await db.execute(sa.select(User).where(User.email == email))
        stale = result.scalar_one_or_none()
        if stale:
            logger.warning(
                "UUID mismatch for %s: DB has %s, JWT has %s — purging stale user",
                email, stale.id, user_id,
            )
            await db.delete(stale)
            await db.commit()

    if existing:
        # Refresh name/email in case they changed in Supabase
        existing.name = name
        existing.email = email
        await db.commit()
        await db.refresh(existing)
        return existing

    new_user = User(id=user_id, name=name, email=email)
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    await db.commit()

    logger.info("Synced new user %s (%s)", user_id, email)
    return new_user
