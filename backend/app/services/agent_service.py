import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agents import Agent
from app.schemas.agents import AgentCreate, AgentUpdate


async def create_agent(db: AsyncSession, data: AgentCreate) -> Agent:
    agent = Agent(**data.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def get_agent(db: AsyncSession, agent_id: uuid.UUID) -> Optional[Agent]:
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def list_agents(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Agent]:
    result = await db.execute(
        select(Agent)
        .where(Agent.is_active.is_(True))
        .order_by(Agent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_agent(
    db: AsyncSession, agent_id: uuid.UUID, data: AgentUpdate
) -> Optional[Agent]:
    agent = await get_agent(db, agent_id)
    if agent is None:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)
    await db.commit()
    await db.refresh(agent)
    return agent


async def delete_agent(db: AsyncSession, agent_id: uuid.UUID) -> bool:
    """Soft delete."""
    agent = await get_agent(db, agent_id)
    if agent is None:
        return False
    agent.is_active = False
    await db.commit()
    return True
