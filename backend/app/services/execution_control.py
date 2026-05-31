"""Workflow execution control — pause, resume, terminate, retry.

Architecture:
  - Control signals live in Redis (fast, no DB round-trip per node).
  - Each node_fn polls the signal key at its START so the graph responds
    at the next node boundary (not mid-LLM-call — that would be unsafe).
  - Pause saves no extra state: on resume the executor re-runs the full
    graph, but node_fns skip nodes that already have a completed WorkflowStep.
  - Retry (failed run): same as resume — just re-queue the Celery task;
    completed steps are naturally skipped by the idempotency check.

Signal lifecycle:
  pause     → executor catches PauseSignal, marks status="paused", keeps signal in Redis
  terminate → executor catches TerminateSignal, marks status="cancelled", clears signal
  resume    → clear signal, set status="pending", re-enqueue Celery task
  retry     → same as resume but also clears the error_message
"""
import json
import logging
import uuid

logger = logging.getLogger(__name__)

_SIGNAL_KEY = "exec:signal:{id}"
_SIGNAL_TTL = 3600  # 1 hour


class PauseSignal(Exception):
    pass


class TerminateSignal(Exception):
    pass


def _key(execution_id: str) -> str:
    return _SIGNAL_KEY.format(id=execution_id)


async def send_pause(execution_id: str) -> None:
    import redis.asyncio as aioredis
    from app.core.config import settings
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        await r.set(_key(execution_id), "pause", ex=_SIGNAL_TTL)
    finally:
        await r.aclose()


async def send_terminate(execution_id: str) -> None:
    import redis.asyncio as aioredis
    from app.core.config import settings
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        await r.set(_key(execution_id), "terminate", ex=_SIGNAL_TTL)
    finally:
        await r.aclose()


async def clear_signal(execution_id: str) -> None:
    import redis.asyncio as aioredis
    from app.core.config import settings
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        await r.delete(_key(execution_id))
    finally:
        await r.aclose()


async def get_signal(execution_id: str) -> str | None:
    """Returns 'pause', 'terminate', or None. Called by node_fns at node start."""
    import redis.asyncio as aioredis
    from app.core.config import settings
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        val = await r.get(_key(execution_id))
        return val.decode() if val else None
    except Exception:
        return None
    finally:
        await r.aclose()


# ── DB-level operations (called by API endpoints) ──────────────────────────────

async def pause_execution(execution_id: str, user_id: uuid.UUID) -> dict:
    """Signal the running executor to pause at the next node boundary."""
    from sqlalchemy import select
    from app.db.base import get_session_factory
    from app.db.models.workflows import WorkflowExecution

    async with get_session_factory()() as db:
        ex = (await db.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.user_id == user_id,
            )
        )).scalar_one_or_none()
        if ex is None:
            return {"error": "Execution not found"}
        if ex.status not in ("running", "pending"):
            return {"error": f"Cannot pause execution in status '{ex.status}'"}

    await send_pause(str(execution_id))
    return {"ok": True, "action": "pause", "execution_id": str(execution_id)}


async def terminate_execution(execution_id: str, user_id: uuid.UUID) -> dict:
    """Signal the executor to stop immediately and mark as cancelled."""
    from sqlalchemy import select
    from app.db.base import get_session_factory
    from app.db.models.workflows import WorkflowExecution

    async with get_session_factory()() as db:
        ex = (await db.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.user_id == user_id,
            )
        )).scalar_one_or_none()
        if ex is None:
            return {"error": "Execution not found"}
        if ex.status in ("completed", "cancelled"):
            return {"error": f"Execution already in terminal status '{ex.status}'"}

    await send_terminate(str(execution_id))
    return {"ok": True, "action": "terminate", "execution_id": str(execution_id)}


async def resume_execution(execution_id: str, user_id: uuid.UUID) -> dict:
    """Re-queue a paused or failed execution. Completed steps are skipped automatically."""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.db.base import get_session_factory
    from app.db.models.workflows import WorkflowExecution

    async with get_session_factory()() as db:
        ex = (await db.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.user_id == user_id,
            )
        )).scalar_one_or_none()
        if ex is None:
            return {"error": "Execution not found"}
        if ex.status not in ("paused", "failed"):
            return {"error": f"Can only resume paused or failed executions (current: '{ex.status}')"}

        # Clear any lingering control signal and reset to pending
        await clear_signal(str(execution_id))
        ex.status = "pending"
        ex.error_message = None
        ex.started_at = datetime.now(timezone.utc)
        await db.commit()
        ex_id = ex.id

    # Re-enqueue as a new Celery task
    from app.worker.tasks import execute_workflow as run_task
    task = run_task.delay(str(ex_id))

    async with get_session_factory()() as db:
        ex = (await db.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == ex_id)
        )).scalar_one()
        ex.celery_task_id = task.id
        await db.commit()

    logger.info("Resumed execution %s as Celery task %s", ex_id, task.id)
    return {"ok": True, "action": "resume", "execution_id": str(ex_id), "celery_task_id": task.id}
