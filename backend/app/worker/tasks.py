import asyncio
import logging

from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.worker.tasks.execute_workflow")
def execute_workflow(self, execution_id: str) -> None:
    """Run a full workflow execution. ONE Celery task per execution — LangGraph
    walks the graph internally (sequential, parallel, or supervisor-routed)."""
    logger.info("Starting workflow execution %s (task %s)", execution_id, self.request.id)
    asyncio.run(_run(execution_id))


async def _run(execution_id: str) -> None:
    from app.db.base import create_worker_engine_and_factory, set_worker_session_factory
    from app.core.workflow.executor import run_workflow_execution

    # Fresh engine bound to THIS task's event loop (asyncio.run creates a new
    # loop per task). Avoids "future attached to a different loop" from the
    # shared singleton engine.
    engine, factory = create_worker_engine_and_factory()
    set_worker_session_factory(factory)
    try:
        await run_workflow_execution(execution_id)
    finally:
        set_worker_session_factory(None)
        await engine.dispose()


@celery_app.task(name="app.worker.tasks.check_due_schedules")
def check_due_schedules() -> None:
    """Fires any workflow schedules whose next_run_at has passed. Runs every 60s via Celery Beat."""
    asyncio.run(_check_schedules())


async def _check_schedules() -> None:
    from app.db.base import create_worker_engine_and_factory, set_worker_session_factory
    from app.services import workflow_service

    engine, factory = create_worker_engine_and_factory()
    set_worker_session_factory(factory)
    try:
        async with factory() as db:
            due = await workflow_service.get_due_schedules(db)
            for sched in due:
                logger.info("Firing schedule %s for workflow %s", sched.id, sched.workflow_id)
                execution_id = await workflow_service.fire_schedule(db, sched)
                if execution_id:
                    task = execute_workflow.delay(execution_id)
                    # store celery task id
                    async with factory() as db2:
                        import uuid
                        await workflow_service.set_celery_task_id(
                            db2, uuid.UUID(execution_id), task.id
                        )
    finally:
        set_worker_session_factory(None)
        await engine.dispose()
