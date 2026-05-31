import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workflows import Workflow, WorkflowExecution, WorkflowStep, ExecutionEvent
from app.schemas.workflows import WorkflowCreate, WorkflowUpdate
from app.db.models.agents import Agent


# ── Workflow CRUD (user-isolated) ────────────────────────────────────────────

async def create_workflow(db: AsyncSession, data: WorkflowCreate, user_id: uuid.UUID) -> Workflow:
    workflow = Workflow(**data.model_dump(), user_id=user_id)
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def get_workflow(
    db: AsyncSession, workflow_id: uuid.UUID, user_id: Optional[uuid.UUID] = None
) -> Optional[Workflow]:
    filters = [Workflow.id == workflow_id, Workflow.is_active.is_(True)]
    if user_id is not None:
        filters.append(Workflow.user_id == user_id)
    result = await db.execute(select(Workflow).where(*filters))
    return result.scalar_one_or_none()


async def list_workflows(
    db: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[Workflow]:
    result = await db.execute(
        select(Workflow)
        .where(Workflow.user_id == user_id, Workflow.is_active.is_(True))
        .order_by(Workflow.created_at.desc())
        .offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def update_workflow(
    db: AsyncSession, workflow_id: uuid.UUID, data: WorkflowUpdate, user_id: uuid.UUID
) -> Optional[Workflow]:
    workflow = await get_workflow(db, workflow_id, user_id)
    if workflow is None:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(workflow, key, value)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def delete_workflow(db: AsyncSession, workflow_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    workflow = await get_workflow(db, workflow_id, user_id)
    if workflow is None:
        return False
    workflow.is_active = False
    await db.commit()
    return True


# ── Executions ───────────────────────────────────────────────────────────────

async def create_execution(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    user_id: uuid.UUID,
    input_data: dict,
    trigger_type: str,
    trigger_context: dict,
) -> WorkflowExecution:
    ex = WorkflowExecution(
        workflow_id=workflow_id,
        user_id=user_id,
        status="pending",
        trigger_type=trigger_type,
        trigger_context=trigger_context,
        input_data=input_data,
    )
    db.add(ex)
    await db.commit()
    await db.refresh(ex)
    return ex


async def set_celery_task_id(db: AsyncSession, execution_id: uuid.UUID, task_id: str) -> None:
    ex = (await db.execute(
        select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
    )).scalar_one()
    ex.celery_task_id = task_id
    await db.commit()


async def get_execution(
    db: AsyncSession, execution_id: uuid.UUID, user_id: uuid.UUID
) -> Optional[WorkflowExecution]:
    result = await db.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_executions(
    db: AsyncSession, workflow_id: uuid.UUID, user_id: uuid.UUID, skip: int = 0, limit: int = 50
) -> list[WorkflowExecution]:
    result = await db.execute(
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id, WorkflowExecution.user_id == user_id)
        .order_by(WorkflowExecution.created_at.desc())
        .offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def list_steps(db: AsyncSession, execution_id: uuid.UUID) -> list[WorkflowStep]:
    result = await db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.execution_id == execution_id)
        .order_by(WorkflowStep.created_at.asc())
    )
    return list(result.scalars().all())


async def list_all_executions(
    db: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 50
) -> list[tuple]:
    """List all executions for a user across all workflows, with the workflow name."""
    result = await db.execute(
        select(WorkflowExecution, Workflow.name)
        .join(Workflow, WorkflowExecution.workflow_id == Workflow.id)
        .where(WorkflowExecution.user_id == user_id)
        .order_by(WorkflowExecution.created_at.desc())
        .offset(skip).limit(limit)
    )
    return list(result.all())


async def get_execution_trace(
    db: AsyncSession, execution_id: uuid.UUID, user_id: uuid.UUID
) -> Optional[dict]:
    """Return a fully assembled trace tree: execution root + per-node spans enriched
    with agent metadata, timing, and token/cost usage."""
    ex = await get_execution(db, execution_id, user_id)
    if ex is None:
        return None

    wf_result = await db.execute(
        select(Workflow.name, Workflow.graph_json).where(Workflow.id == ex.workflow_id)
    )
    wf_row = wf_result.first()
    workflow_name = wf_row[0] if wf_row else "Unknown Workflow"
    graph_json = wf_row[1] if wf_row else {}

    # Build node label/type lookup from graph_json
    node_map: dict[str, dict] = {}
    for node in (graph_json.get("nodes") or []):
        nid = node.get("id", "")
        node_map[nid] = {
            "label": node.get("data", {}).get("label") or nid,
            "type": node.get("type", "agent"),
        }

    steps = await list_steps(db, execution_id)

    # Load agents referenced by steps in one batch query
    agent_ids = {s.agent_id for s in steps if s.agent_id is not None}
    agents: dict[uuid.UUID, Agent] = {}
    if agent_ids:
        agent_rows = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
        for a in agent_rows.scalars().all():
            agents[a.id] = a

    # Load tool/decision events for all steps in one query
    events_result = await db.execute(
        select(ExecutionEvent)
        .where(
            ExecutionEvent.execution_id == execution_id,
            ExecutionEvent.event_type.in_(["tool_start", "tool_end", "supervisor_decision"]),
        )
        .order_by(ExecutionEvent.created_at.asc())
    )
    events_by_step: dict[uuid.UUID, list] = {}
    for ev in events_result.scalars().all():
        if ev.step_id:
            events_by_step.setdefault(ev.step_id, []).append({
                "id": str(ev.id),
                "event_type": ev.event_type,
                "payload": ev.payload or {},
                "created_at": ev.created_at,
            })

    exec_duration_ms = None
    if ex.started_at and ex.completed_at:
        exec_duration_ms = int((ex.completed_at - ex.started_at).total_seconds() * 1000)

    spans = []
    total_in_tok = 0
    total_out_tok = 0
    total_cost = 0.0

    for step in steps:
        node_info = node_map.get(step.node_id, {"label": step.node_id, "type": "agent"})
        agent = agents.get(step.agent_id) if step.agent_id else None

        usage = (step.output or {}).get("usage", {}) or {}
        in_tok = usage.get("input_tokens")
        out_tok = usage.get("output_tokens")
        cost = usage.get("cost_usd")

        total_in_tok += in_tok or 0
        total_out_tok += out_tok or 0
        total_cost += cost or 0.0

        duration_ms = None
        if step.started_at and step.completed_at:
            duration_ms = int((step.completed_at - step.started_at).total_seconds() * 1000)

        spans.append({
            "id": step.id,
            "node_id": step.node_id,
            "node_label": node_info["label"],
            "span_type": node_info["type"],
            "agent_name": agent.name if agent else None,
            "model": agent.model if agent else None,
            "provider": agent.provider if agent else None,
            "max_tokens": agent.max_tokens if agent else None,
            "status": step.status,
            "started_at": step.started_at,
            "completed_at": step.completed_at,
            "duration_ms": duration_ms,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": cost,
            "input": step.input or {},
            "output": step.output,
            "error_message": step.error_message,
            "events": events_by_step.get(step.id, []),
        })

    return {
        "execution_id": ex.id,
        "workflow_id": ex.workflow_id,
        "workflow_name": workflow_name,
        "status": ex.status,
        "trigger_type": ex.trigger_type,
        "input_text": (ex.input_data or {}).get("input", ""),
        "output_text": (ex.output_data or {}).get("output"),
        "error_message": ex.error_message,
        "started_at": ex.started_at,
        "completed_at": ex.completed_at,
        "duration_ms": exec_duration_ms,
        "total_input_tokens": total_in_tok,
        "total_output_tokens": total_out_tok,
        "total_cost_usd": round(total_cost, 8),
        "spans": spans,
    }


async def mark_cancelled(db: AsyncSession, execution_id: uuid.UUID) -> None:
    from datetime import datetime, timezone

    ex = (await db.execute(
        select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
    )).scalar_one()
    ex.status = "cancelled"
    ex.completed_at = datetime.now(timezone.utc)
    await db.commit()
