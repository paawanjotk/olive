import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session_factory
from app.schemas.agents import AgentCreate, AgentUpdate, AgentResponse, AgentTestRequest, AgentTestResponse
from app.services import agent_service

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_db():
    factory = get_session_factory()
    async with factory() as session:
        yield session


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
):
    agent = await agent_service.create_agent(db, body)
    return agent


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await agent_service.list_agents(db, skip=skip, limit=limit)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    agent = await agent_service.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    db: AsyncSession = Depends(get_db),
):
    agent = await agent_service.update_agent(db, agent_id, body)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    deleted = await agent_service.delete_agent(db, agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")


@router.post("/{agent_id}/test", response_model=AgentTestResponse)
async def test_agent(
    agent_id: uuid.UUID,
    body: AgentTestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run a single message against an agent and return the full response (non-streaming)."""
    agent = await agent_service.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    from app.core.agent.config import AgentConfig
    from app.core.agent.loop import run_agent_turn

    config = AgentConfig.from_db(agent)
    messages = [{"role": "user", "content": body.message}]

    collected = []
    provider_used = config.provider

    try:
        async for event in run_agent_turn(
            messages=messages,
            agent_config=config,
            session_id=None,
            user_id=None,
            conversation_id=None,
            cancel_event=None,
        ):
            if event["type"] == "chunk":
                collected.append(event["content"])
            elif event["type"] == "provider_fallback":
                provider_used = event["to"]
    except Exception as e:
        logger.error("Agent test failed for %s: %s", agent_id, e)
        raise HTTPException(status_code=500, detail=f"Agent test failed: {e}")

    return AgentTestResponse(
        response="".join(collected),
        provider_used=provider_used,
    )
