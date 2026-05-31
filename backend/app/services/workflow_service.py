import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workflows import Workflow, WorkflowExecution, WorkflowStep
from app.schemas.workflows import WorkflowCreate, WorkflowUpdate


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


async def mark_cancelled(db: AsyncSession, execution_id: uuid.UUID) -> None:
    from datetime import datetime, timezone

    ex = (await db.execute(
        select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
    )).scalar_one()
    ex.status = "cancelled"
    ex.completed_at = datetime.now(timezone.utc)
    await db.commit()
