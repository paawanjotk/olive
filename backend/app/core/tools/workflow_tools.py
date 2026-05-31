"""Workflow management tools for the chat agent.

These tools allow the chat agent to trigger and monitor workflows on behalf of
the user. User context (user_id) is injected via a ContextVar set by the agent
loop before each turn.
"""
import json
import logging
import uuid
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger(__name__)

# Injected before each agent turn; tools read this to scope DB queries.
_tool_user_id: ContextVar[Optional[str]] = ContextVar("_tool_user_id", default=None)


def set_tool_user_id(user_id: str) -> None:
    """Call this before running an agent turn to inject the user context."""
    _tool_user_id.set(user_id)


def get_tool_user_id() -> Optional[str]:
    return _tool_user_id.get()


async def tool_list_workflows(limit: int = 10, **_) -> str:
    """List the user's workflows."""
    user_id_str = get_tool_user_id()
    if not user_id_str:
        return json.dumps({"error": "No user context available"})
    try:
        from app.db.base import get_session_factory
        from app.services import workflow_service
        async with get_session_factory()() as db:
            workflows = await workflow_service.list_workflows(db, uuid.UUID(user_id_str), limit=min(limit, 20))
        result = [
            {"id": str(wf.id), "name": wf.name, "description": wf.description,
             "node_count": len((wf.graph_json or {}).get("nodes", []))}
            for wf in workflows
        ]
        return json.dumps({"workflows": result, "count": len(result)})
    except Exception as e:
        logger.exception("tool_list_workflows failed")
        return json.dumps({"error": str(e)})


async def tool_run_workflow(workflow_id: str, input_text: str = "", **_) -> str:
    """Trigger a workflow execution. Returns the execution_id to track progress."""
    user_id_str = get_tool_user_id()
    if not user_id_str:
        return json.dumps({"error": "No user context available"})
    try:
        from app.db.base import get_session_factory
        from app.services import workflow_service
        user_id = uuid.UUID(user_id_str)
        async with get_session_factory()() as db:
            wf = await workflow_service.get_workflow(db, uuid.UUID(workflow_id), user_id)
            if wf is None:
                return json.dumps({"error": f"Workflow {workflow_id} not found"})
            ex = await workflow_service.create_execution(
                db, wf.id, user_id,
                input_data={"input": input_text},
                trigger_type="chat",
                trigger_context={"platform": "chat", "user_id": user_id_str},
            )
            execution_id = str(ex.id)
        from app.worker.tasks import execute_workflow as run_task
        task = run_task.delay(execution_id)
        async with get_session_factory()() as db:
            await workflow_service.set_celery_task_id(db, uuid.UUID(execution_id), task.id)
        return json.dumps({
            "execution_id": execution_id,
            "workflow_name": wf.name,
            "status": "running",
            "message": f"Workflow '{wf.name}' is now running. Use get_workflow_status to check progress.",
        })
    except Exception as e:
        logger.exception("tool_run_workflow failed")
        return json.dumps({"error": str(e)})


async def tool_pause_execution(execution_id: str, **_) -> str:
    """Pause a running workflow execution."""
    user_id_str = get_tool_user_id()
    if not user_id_str:
        return json.dumps({"error": "No user context available"})
    try:
        from app.services.execution_control import pause_execution
        result = await pause_execution(execution_id, uuid.UUID(user_id_str))
        if "error" in result:
            return json.dumps(result)
        return json.dumps({"execution_id": execution_id, "status": "pausing", "message": "Pause signal sent. The execution will pause at the next safe checkpoint."})
    except Exception as e:
        logger.exception("tool_pause_execution failed")
        return json.dumps({"error": str(e)})


async def tool_resume_execution(execution_id: str, **_) -> str:
    """Resume a paused workflow execution."""
    user_id_str = get_tool_user_id()
    if not user_id_str:
        return json.dumps({"error": "No user context available"})
    try:
        from app.services.execution_control import resume_execution
        result = await resume_execution(execution_id, uuid.UUID(user_id_str))
        if "error" in result:
            return json.dumps(result)
        return json.dumps({"execution_id": execution_id, "status": "running", "message": "Execution resumed successfully."})
    except Exception as e:
        logger.exception("tool_resume_execution failed")
        return json.dumps({"error": str(e)})


async def tool_terminate_execution(execution_id: str, **_) -> str:
    """Terminate (stop) a running or paused workflow execution immediately."""
    user_id_str = get_tool_user_id()
    if not user_id_str:
        return json.dumps({"error": "No user context available"})
    try:
        from app.services.execution_control import terminate_execution
        result = await terminate_execution(execution_id, uuid.UUID(user_id_str))
        if "error" in result:
            return json.dumps(result)
        return json.dumps({"execution_id": execution_id, "status": "cancelled", "message": "Terminate signal sent. The execution will stop shortly."})
    except Exception as e:
        logger.exception("tool_terminate_execution failed")
        return json.dumps({"error": str(e)})


async def tool_get_workflow_status(execution_id: str, **_) -> str:
    """Get the current status and result of a workflow execution."""
    user_id_str = get_tool_user_id()
    if not user_id_str:
        return json.dumps({"error": "No user context available"})
    try:
        from app.db.base import get_session_factory
        from app.services import workflow_service
        async with get_session_factory()() as db:
            ex = await workflow_service.get_execution(db, uuid.UUID(execution_id), uuid.UUID(user_id_str))
            if ex is None:
                return json.dumps({"error": f"Execution {execution_id} not found"})
            steps = await workflow_service.list_steps(db, uuid.UUID(execution_id))
        step_summaries = [
            {"node_id": s.node_id, "status": s.status,
             "output_preview": (((s.output or {}).get("text") or "")[:200]) if s.output else ""}
            for s in steps
        ]
        output_preview = ""
        if ex.output_data:
            output_preview = (ex.output_data.get("output") or "")[:500]
        return json.dumps({
            "execution_id": execution_id,
            "status": ex.status,
            "started_at": ex.started_at.isoformat() if ex.started_at else None,
            "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
            "error": ex.error_message,
            "steps": step_summaries,
            "output_preview": output_preview,
        })
    except Exception as e:
        logger.exception("tool_get_workflow_status failed")
        return json.dumps({"error": str(e)})
