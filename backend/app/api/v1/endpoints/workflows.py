import asyncio
import json
import logging
import uuid
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.workflow.events import channel_for
from app.db.base import get_session_factory
from app.dependencies.auth import get_current_user, verify_websocket_token
from app.schemas.workflows import (
    ExecuteWorkflowRequest,
    ExecutionWithWorkflowResponse,
    WorkflowCreate,
    WorkflowExecutionResponse,
    WorkflowResponse,
    WorkflowStepResponse,
    WorkflowUpdate,
)
from app.services import workflow_service

router = APIRouter()
logger = logging.getLogger(__name__)


class ApproveCheckpointRequest(BaseModel):
    node_id: str
    approved: bool = True
    reason: str = ""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


def _uid(current_user: dict) -> uuid.UUID:
    return uuid.UUID(current_user["id"])


# ── Execution-scoped routes (declared first so the literal "executions"
#    segment is matched before the dynamic /{workflow_id}) ────────────────────

@router.get("/executions", response_model=list[ExecutionWithWorkflowResponse])
async def list_all_executions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all executions for the current user across all workflows."""
    rows = await workflow_service.list_all_executions(db, _uid(current_user), skip=skip, limit=limit)
    result = []
    for ex, workflow_name in rows:
        ex_dict = {
            "id": ex.id,
            "workflow_id": ex.workflow_id,
            "user_id": ex.user_id,
            "status": ex.status,
            "trigger_type": ex.trigger_type,
            "trigger_context": ex.trigger_context or {},
            "input_data": ex.input_data or {},
            "output_data": ex.output_data,
            "error_message": ex.error_message,
            "celery_task_id": ex.celery_task_id,
            "started_at": ex.started_at,
            "completed_at": ex.completed_at,
            "created_at": ex.created_at,
            "workflow_name": workflow_name,
        }
        result.append(ex_dict)
    return result


@router.get("/executions/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_execution(
    execution_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ex = await workflow_service.get_execution(db, execution_id, _uid(current_user))
    if ex is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return ex


@router.get("/executions/{execution_id}/steps", response_model=list[WorkflowStepResponse])
async def list_steps(
    execution_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ex = await workflow_service.get_execution(db, execution_id, _uid(current_user))
    if ex is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return await workflow_service.list_steps(db, execution_id)


@router.get("/executions/{execution_id}/stream")
async def stream_execution(
    execution_id: uuid.UUID,
    token: str = Query(..., description="Supabase access token (SSE can't send headers)"),
):
    """Server-Sent Events: subscribe to the Redis channel the worker publishes to
    and relay events live to the browser."""
    user = await verify_websocket_token(token)
    async with get_session_factory()() as db:
        ex = await workflow_service.get_execution(db, execution_id, uuid.UUID(user["id"]))
        if ex is None:
            raise HTTPException(status_code=404, detail="Execution not found")

    async def event_stream() -> AsyncGenerator[str, None]:
        redis = aioredis.from_url(settings.REDIS_URL)
        pubsub = redis.pubsub()
        channel = channel_for(str(execution_id))
        await pubsub.subscribe(channel)
        # Tell the client the stream is open even before the first worker event.
        yield 'data: {"type": "stream_open"}\n\n'
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30.0)
                if message is None:
                    yield ": keepalive\n\n"  # SSE comment — keeps the connection warm
                    continue
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                yield f"data: {data}\n\n"
                try:
                    if json.loads(data).get("type") in (
                        "execution_completed", "execution_failed", "execution_paused",
                    ):
                        break
                except (json.JSONDecodeError, AttributeError):
                    pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            await redis.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/executions/{execution_id}/approve", status_code=204)
async def approve_checkpoint(
    execution_id: uuid.UUID,
    body: ApproveCheckpointRequest,
    current_user: dict = Depends(get_current_user),
):
    """Signal approval or rejection for a blocking human checkpoint."""
    approval_key = f"approval:{execution_id}:{body.node_id}"
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        await r.lpush(approval_key, json.dumps({"approved": body.approved, "reason": body.reason}))
        await r.expire(approval_key, 60)
    finally:
        await r.aclose()


@router.post("/executions/{execution_id}/pause")
async def pause_execution(
    execution_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    from app.services.execution_control import pause_execution as _pause
    result = await _pause(str(execution_id), _uid(current_user))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/executions/{execution_id}/resume")
async def resume_execution(
    execution_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    from app.services.execution_control import resume_execution as _resume
    result = await _resume(str(execution_id), _uid(current_user))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/executions/{execution_id}/terminate")
async def terminate_execution(
    execution_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    from app.services.execution_control import terminate_execution as _terminate
    result = await _terminate(str(execution_id), _uid(current_user))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/executions/{execution_id}/cancel", status_code=204)
async def cancel_execution(
    execution_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ex = await workflow_service.get_execution(db, execution_id, _uid(current_user))
    if ex is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    if ex.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="Execution is not cancellable")
    if ex.celery_task_id:
        from app.worker import celery_app
        celery_app.control.revoke(ex.celery_task_id, terminate=True)
    await workflow_service.mark_cancelled(db, execution_id)


# ── Templates (literal segment, declared before /{workflow_id}) ──────────────

@router.get("/templates")
async def list_templates(current_user: dict = Depends(get_current_user)):
    from app.core.workflow.templates import list_templates as _list
    return _list()


@router.post("/templates/{key}/clone", response_model=WorkflowResponse, status_code=201)
async def clone_template(
    key: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.core.workflow.templates import instantiate_template
    try:
        return await instantiate_template(db, key, _uid(current_user))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown template: {key}")


# ── Workflow CRUD ─────────────────────────────────────────────────────────────

@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    body: WorkflowCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await workflow_service.create_workflow(db, body, _uid(current_user))


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await workflow_service.list_workflows(db, _uid(current_user), skip=skip, limit=limit)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wf = await workflow_service.get_workflow(db, workflow_id, _uid(current_user))
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    body: WorkflowUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wf = await workflow_service.update_workflow(db, workflow_id, body, _uid(current_user))
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await workflow_service.delete_workflow(db, workflow_id, _uid(current_user))
    if not deleted:
        raise HTTPException(status_code=404, detail="Workflow not found")


@router.get("/{workflow_id}/executions", response_model=list[WorkflowExecutionResponse])
async def list_workflow_executions(
    workflow_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wf = await workflow_service.get_workflow(db, workflow_id, _uid(current_user))
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return await workflow_service.list_executions(db, workflow_id, _uid(current_user), skip=skip, limit=limit)


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse, status_code=202)
async def execute_workflow(
    workflow_id: uuid.UUID,
    body: ExecuteWorkflowRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = _uid(current_user)
    wf = await workflow_service.get_workflow(db, workflow_id, user_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    ex = await workflow_service.create_execution(
        db, workflow_id, user_id,
        input_data={"input": body.input},
        trigger_type=body.trigger_type,
        trigger_context=body.trigger_context,
    )

    # Enqueue the run; store the Celery task id so we can revoke/monitor it.
    from app.worker.tasks import execute_workflow as run_task
    task = run_task.delay(str(ex.id))
    await workflow_service.set_celery_task_id(db, ex.id, task.id)
    await db.refresh(ex)
    return ex
