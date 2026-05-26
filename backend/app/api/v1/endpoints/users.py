import uuid
import logging

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models.users import User
from app.schemas.users import UserCreate, UserResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def create_or_get_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user or return existing user by email."""
    email = user_in.email.strip().lower()

    # Check if user already exists
    result = await db.execute(
        sa.select(User).where(User.email == email)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user is not None:
        logger.info(f"Returning existing user {existing_user.id} for email {email}")
        return existing_user

    # Create new user
    new_user = User(
        id=uuid.uuid4(),
        name=user_in.name.strip(),
        email=email,
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    await db.commit()

    logger.info(f"Created new user {new_user.id} with email {email}")
    return new_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a user by ID."""
    result = await db.execute(
        sa.select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    return user
