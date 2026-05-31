"""Top-level workflow execution entry point, invoked inside the Celery task.

ONE invocation = one full workflow run. Loads the blueprint, resolves each
node's agent, compiles the LangGraph, runs it to completion, streams events
over Redis, and persists status/output. LangGraph handles all internal routing
(sequential, deterministic, or supervisor-delegated)."""
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.workflow.events import EventBus
from app.core.workflow.graph_builder import build_graph
from app.core.workflow.node_runner import (
    make_agent_node,
    make_checkpoint_node,
    make_supervisor_node,
)
from app.db.base import get_session_factory
from app.db.models.agents import Agent
from app.db.models.workflows import Workflow, WorkflowExecution

logger = logging.getLogger(__name__)


async def _load(execution_id: str):
    async with get_session_factory()() as db:
        ex = (await db.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == uuid.UUID(execution_id))
        )).scalar_one_or_none()
        if ex is None:
            return None, None
        wf = (await db.execute(
            select(Workflow).where(Workflow.id == ex.workflow_id)
        )).scalar_one_or_none()
        return ex, wf


async def _set_running(execution_id: str) -> None:
    async with get_session_factory()() as db:
        ex = (await db.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == uuid.UUID(execution_id))
        )).scalar_one()
        ex.status = "running"
        ex.started_at = datetime.now(timezone.utc)
        await db.commit()


async def _finalize(execution_id: str, status: str, output: dict | None, error: str | None) -> None:
    async with get_session_factory()() as db:
        ex = (await db.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == uuid.UUID(execution_id))
        )).scalar_one()
        ex.status = status
        ex.output_data = output
        ex.error_message = error
        ex.completed_at = datetime.now(timezone.utc)
        await db.commit()


async def _resolve_agents(graph_json: dict, user_id) -> dict[str, Agent]:
    """node_id -> Agent for every node carrying an agentId."""
    wanted = {}
    for n in graph_json.get("nodes", []):
        aid = n.get("data", {}).get("agentId") or n.get("agent_id")
        if aid:
            wanted[n["id"]] = uuid.UUID(str(aid))
    if not wanted:
        return {}
    async with get_session_factory()() as db:
        rows = (await db.execute(
            select(Agent).where(Agent.id.in_(set(wanted.values())))
        )).scalars().all()
        by_id = {a.id: a for a in rows}
    return {nid: by_id[aid] for nid, aid in wanted.items() if aid in by_id}


def _worker_specs(graph_json: dict, supervisor_id: str, agents: dict[str, Agent]) -> list[dict]:
    """Outgoing executable targets of a supervisor, described for the routing prompt."""
    by_id = {n["id"]: n for n in graph_json.get("nodes", [])}
    specs = []
    for e in graph_json.get("edges", []):
        if e["source"] != supervisor_id:
            continue
        t = e["target"]
        node = by_id.get(t)
        if node is None or node.get("type") in ("end", "trigger", "start"):
            continue
        data = node.get("data", {})
        agent = agents.get(t)
        desc = data.get("description") or (getattr(agent, "description", "") if agent else "") or ""
        specs.append({"id": t, "label": data.get("label") or t, "description": desc})
    return specs


async def _post_slack_workflow_start(
    trigger_context: dict, workflow_name: str, execution_id: str
) -> None:
    """Post a workflow-start notification to the originating Slack thread."""
    if not trigger_context or trigger_context.get("platform") != "slack":
        return
    channel_id = trigger_context.get("channel_id")
    thread_ts = trigger_context.get("thread_ts")
    if not channel_id:
        return
    try:
        from app.services import slack_service
        await slack_service.send_message(
            channel_id,
            f"🚀 *{workflow_name}* started  _(execution `{execution_id[:8]}`)_",
            thread_ts=thread_ts,
        )
    except Exception as e:
        logger.warning("Slack workflow start post failed: %s", e)


async def run_workflow_execution(execution_id: str) -> None:
    bus = EventBus(execution_id)
    try:
        ex, wf = await _load(execution_id)
        if ex is None or wf is None:
            logger.error("Execution or workflow missing for %s", execution_id)
            return

        await _set_running(execution_id)
        await bus.publish("execution_started", workflow_id=str(wf.id), name=wf.name)

        trigger_context = ex.trigger_context or {}
        graph_json = wf.graph_json or {}
        agents = await _resolve_agents(graph_json, ex.user_id)

        # Identify the end node id so supervisors can emit it in events instead of "__end__".
        end_ids = [n["id"] for n in graph_json.get("nodes", []) if n.get("type") == "end"]
        end_node_id = end_ids[0] if end_ids else "end"

        # Build a node function for each executable node.
        node_fn_map = {}
        for n in graph_json.get("nodes", []):
            nid, ntype = n["id"], (n.get("type") or "agent")
            if ntype in ("trigger", "start", "end"):
                continue
            if ntype == "checkpoint":
                data = n.get("data", {}) or {}
                node_fn_map[nid] = make_checkpoint_node(
                    nid, bus,
                    approval_mode=data.get("approval_mode", "web"),
                    trigger_context=trigger_context,
                    label=data.get("label", "Human checkpoint"),
                )
            elif ntype == "supervisor":
                agent = agents.get(nid)
                if agent is None:
                    raise ValueError(f"Supervisor node '{nid}' has no agent assigned")
                node_fn_map[nid] = make_supervisor_node(
                    nid, agent, _worker_specs(graph_json, nid, agents), bus,
                    end_node_id=end_node_id,
                    trigger_context=trigger_context,
                )
            else:  # agent
                agent = agents.get(nid)
                if agent is None:
                    raise ValueError(f"Agent node '{nid}' has no agent assigned")
                node_fn_map[nid] = make_agent_node(nid, agent, bus, trigger_context=trigger_context)

        if not node_fn_map:
            raise ValueError("Workflow has no executable nodes")

        compiled = build_graph(graph_json, node_fn_map)

        input_text = (ex.input_data or {}).get("input", "")
        initial: dict = {
            "execution_id": execution_id,
            "original_input": input_text,
            "messages": [{"role": "user", "content": input_text}],
            "node_outputs": {},
            "next": "",
            "iterations": 0,
        }

        # Post a workflow start notification to the originating Slack thread.
        await _post_slack_workflow_start(trigger_context, wf.name, execution_id)

        # recursion_limit guards pathological supervisor loops at the graph level too.
        final_state = await compiled.ainvoke(initial, {"recursion_limit": 50})

        final_output = _final_output(final_state)
        await _finalize(execution_id, "completed",
                        {"output": final_output, "node_outputs": final_state.get("node_outputs", {})}, None)

        # Deliver the result back to the originating channel, if any.
        await _deliver_to_channel(trigger_context, final_output, bus)

        await bus.publish("execution_completed", output=final_output)

    except Exception as e:
        logger.exception("Workflow execution %s failed", execution_id)
        await _finalize(execution_id, "failed", None, str(e))
        await bus.publish("execution_failed", error=str(e))
    finally:
        await bus.close()


async def _deliver_to_channel(trigger_context: dict, output: str, bus: EventBus) -> None:
    """If the run was triggered from a messaging channel, send the result back."""
    platform = (trigger_context or {}).get("platform")
    if platform == "telegram":
        chat_id = trigger_context.get("chat_id")
        if chat_id:
            try:
                from app.services import telegram_service
                await telegram_service.send_message(chat_id, output)
                await bus.publish("output_sent", platform="telegram", chat_id=chat_id)
            except Exception as e:
                logger.warning("Telegram delivery failed: %s", e)
    elif platform == "slack":
        channel_id = trigger_context.get("channel_id")
        thread_ts = trigger_context.get("thread_ts")
        if channel_id:
            try:
                from app.services import slack_service
                await slack_service.send_message(channel_id, output, thread_ts=thread_ts)
                await bus.publish("output_sent", platform="slack", channel_id=channel_id)
            except Exception as e:
                logger.warning("Slack delivery failed: %s", e)


def _final_output(state: dict) -> str:
    """The last assistant turn is the final node's output; strip the [node] tag."""
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "assistant":
            return re.sub(r"^\[[^\]]+\]\s*", "", msg.get("content", ""))
    outputs = list(state.get("node_outputs", {}).values())
    return outputs[-1] if outputs else ""
