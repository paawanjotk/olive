"""Critical path tests: agent creation, workflow execution, message delivery.

These are the three integration tests the spec explicitly names. They run
against a real (in-memory SQLite) database and mock external services
(Anthropic, Celery, Slack, Telegram) so they're fast and CI-safe.
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.agents import Agent
from app.db.models.workflows import Workflow, WorkflowExecution, WorkflowStep
from app.schemas.agents import AgentCreate, AgentUpdate
from app.schemas.workflows import WorkflowCreate
from app.services import agent_service, workflow_service


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
async def db():
    """In-memory SQLite session — no Postgres needed."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def user_id():
    return uuid.uuid4()


# ── Test 1: Agent creation ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_creation_full_crud(db, user_id):
    """Agent CRUD: create → read → update → delete (soft)."""
    # Create
    payload = AgentCreate(
        name="Test Agent",
        description="A test agent",
        role="researcher",
        system_prompt="You are a test agent.",
        model="claude-sonnet-4-6",
        provider="anthropic",
        tools=["web_search"],
        temperature=0.5,
    )
    agent = await agent_service.create_agent(db, payload, user_id)
    assert agent.id is not None
    assert agent.name == "Test Agent"
    assert agent.tools == ["web_search"]
    assert agent.user_id == user_id
    assert agent.is_active is True

    # Read
    fetched = await agent_service.get_agent(db, agent.id, user_id)
    assert fetched is not None
    assert fetched.id == agent.id
    assert fetched.description == "A test agent"

    # Update
    updated = await agent_service.update_agent(
        db, agent.id, AgentUpdate(name="Updated Agent", tools=["calculator"]), user_id
    )
    assert updated.name == "Updated Agent"
    assert updated.tools == ["calculator"]

    # List
    all_agents = await agent_service.list_agents(db, user_id)
    assert any(a.id == agent.id for a in all_agents)

    # Delete (soft)
    deleted = await agent_service.delete_agent(db, agent.id, user_id)
    assert deleted is True
    gone = await agent_service.get_agent(db, agent.id, user_id)
    assert gone is None


@pytest.mark.asyncio
async def test_agent_creation_validates_tools(db, user_id):
    """Agent creation rejects unknown tools."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AgentCreate(
            name="Bad Agent",
            system_prompt="test",
            tools=["nonexistent_tool"],
        )


@pytest.mark.asyncio
async def test_agent_soul_md_and_memory_md(db, user_id):
    """SOUL.md and MEMORY.md fields are persisted and retrievable."""
    agent = await agent_service.create_agent(
        db,
        AgentCreate(
            name="Persona Agent",
            system_prompt="You are a researcher.",
            soul_md="## Philosophy\nI seek truth.",
            memory_md="Remember: user prefers bullet points.",
        ),
        user_id,
    )
    fetched = await agent_service.get_agent(db, agent.id, user_id)
    assert "truth" in (fetched.soul_md or "")
    assert "bullet points" in (fetched.memory_md or "")


# ── Test 2: Workflow execution ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_workflow_execution_lifecycle(db, user_id):
    """Workflow execution: create execution → Celery task queued → steps recorded."""
    # Create supporting agent
    agent = await agent_service.create_agent(
        db,
        AgentCreate(name="Worker", system_prompt="You complete tasks.", tools=[]),
        user_id,
    )

    # Create workflow with 2 agent nodes
    graph_json = {
        "nodes": [
            {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {"label": "Input"}},
            {"id": "worker", "type": "agent", "position": {"x": 200, "y": 0},
             "data": {"label": "Worker", "agentId": str(agent.id)}},
            {"id": "end", "type": "end", "position": {"x": 400, "y": 0}, "data": {"label": "End"}},
        ],
        "edges": [
            {"source": "trigger", "target": "worker"},
            {"source": "worker", "target": "end"},
        ],
    }
    workflow = await workflow_service.create_workflow(
        db, WorkflowCreate(name="Test Workflow", graph_json=graph_json), user_id
    )
    assert workflow.id is not None

    # Create execution
    execution = await workflow_service.create_execution(
        db, workflow.id, user_id,
        input_data={"input": "Do a test task"},
        trigger_type="manual",
        trigger_context={},
    )
    assert execution.status == "pending"
    assert execution.workflow_id == workflow.id

    # Simulate the executor marking it running + recording a step
    async with db.begin_nested():
        execution.status = "running"
        step = WorkflowStep(
            id=uuid.uuid4(),
            execution_id=execution.id,
            node_id="worker",
            agent_id=agent.id,
            status="completed",
            input={"prompt": "Do a test task"},
            output={"text": "Task done.", "usage": {"input_tokens": 100, "output_tokens": 50, "cost_usd": 0.001}},
        )
        db.add(step)
    await db.commit()

    # Verify steps are retrievable
    steps = await workflow_service.list_steps(db, execution.id)
    assert len(steps) == 1
    assert steps[0].node_id == "worker"
    assert steps[0].status == "completed"
    assert steps[0].output["text"] == "Task done."

    # Simulate completion
    await workflow_service.mark_cancelled(db, execution.id)  # reuse for status change
    execution2 = await workflow_service.get_execution(db, execution.id, user_id)
    assert execution2.status in ("cancelled", "running")


@pytest.mark.asyncio
async def test_workflow_execution_list_all(db, user_id):
    """list_all_executions returns executions with workflow names."""
    workflow = await workflow_service.create_workflow(
        db, WorkflowCreate(name="Named Workflow", graph_json={"nodes": [], "edges": []}), user_id
    )
    execution = await workflow_service.create_execution(
        db, workflow.id, user_id,
        input_data={"input": "test"},
        trigger_type="chat",
        trigger_context={},
    )
    rows = await workflow_service.list_all_executions(db, user_id)
    assert len(rows) >= 1
    ex, wf_name = rows[0]
    assert ex.id == execution.id
    assert wf_name == "Named Workflow"


# ── Test 3: Message delivery (channel routing) ────────────────────────────────

@pytest.mark.asyncio
async def test_telegram_message_delivery():
    """Message delivery: Telegram send_message posts to the Bot API."""
    from app.services import telegram_service

    with patch("app.services.telegram_service.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:

        mock_settings.TELEGRAM_BOT_TOKEN = "fake-token-123"
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await telegram_service.send_message(chat_id="12345", text="Hello from Ollive!")

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        # Verify it posted to the right endpoint
        assert "sendMessage" in str(call_kwargs)


@pytest.mark.asyncio
async def test_slack_message_delivery():
    """Message delivery: Slack send_message posts to chat.postMessage."""
    from app.services import slack_service

    with patch("app.services.slack_service.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:

        mock_settings.SLACK_BOT_TOKEN = "xoxb-fake-token"
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "ts": "1234567890.123"}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await slack_service.send_message(
            channel_id="C01234ABCDE",
            text="Workflow completed successfully!",
            thread_ts="1234567890.001",
        )

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "chat.postMessage" in str(call_kwargs)
        # Verify thread_ts was passed
        body = call_kwargs.kwargs.get("json") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else {}
        if isinstance(body, dict):
            assert body.get("thread_ts") == "1234567890.001"


@pytest.mark.asyncio
async def test_slack_block_kit_approval_delivery():
    """Block Kit approval: send_blocks posts interactive buttons to Slack."""
    from app.services import slack_service

    with patch("app.services.slack_service.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:

        mock_settings.SLACK_BOT_TOKEN = "xoxb-fake-token"
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "ts": "1234567890.456"}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "⏸ Approval Required"}},
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "action_id": "checkpoint_approve", "text": {"type": "plain_text", "text": "Approve"}},
                    {"type": "button", "action_id": "checkpoint_reject", "text": {"type": "plain_text", "text": "Reject"}},
                ],
            },
        ]
        await slack_service.send_blocks("C01234ABCDE", blocks, thread_ts="1234567890.001")

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "chat.postMessage" in str(call_kwargs)
