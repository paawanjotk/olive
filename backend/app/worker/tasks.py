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
