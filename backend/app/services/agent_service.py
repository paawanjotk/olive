import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agents import Agent
from app.schemas.agents import AgentCreate, AgentUpdate


async def create_agent(db: AsyncSession, data: AgentCreate, user_id: uuid.UUID) -> Agent:
    agent = Agent(**data.model_dump(), user_id=user_id, is_active=True)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def get_agent(
    db: AsyncSession,
    agent_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
) -> Optional[Agent]:
    filters = [Agent.id == agent_id, Agent.is_active.is_(True)]
    if user_id is not None:
        filters.append(Agent.user_id == user_id)
    result = await db.execute(select(Agent).where(*filters))
    return result.scalar_one_or_none()


async def list_agents(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[Agent]:
    result = await db.execute(
        select(Agent)
        .where(Agent.user_id == user_id, Agent.is_active.is_(True))
        .order_by(Agent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_agent(
    db: AsyncSession,
    agent_id: uuid.UUID,
    data: AgentUpdate,
    user_id: uuid.UUID,
) -> Optional[Agent]:
    agent = await get_agent(db, agent_id, user_id)
    if agent is None:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)
    await db.commit()
    await db.refresh(agent)
    return agent


async def delete_agent(
    db: AsyncSession,
    agent_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    agent = await get_agent(db, agent_id, user_id)
    if agent is None:
        return False
    agent.is_active = False
    await db.commit()
    return True
