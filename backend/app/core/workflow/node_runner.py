"""LangGraph node factories. Each factory returns an async node function that
LangGraph calls with the shared WorkflowState. Nodes run agents via the existing
run_agent_turn loop, persist a workflow_steps row, stream chunks over the event
bus, and return a state delta."""
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select

from app.core.agent.config import AgentConfig
from app.core.agent.loop import run_agent_turn
from app.core.workflow.events import EventBus
from app.core.workflow.state import WorkflowState
from app.db.base import get_session_factory
from app.db.models.workflows import WorkflowStep

logger = logging.getLogger(__name__)


# Rough token/cost estimate. Exact accounting lives in the observe-me traces;
# this gives the monitor a live, good-enough number per step.
_PRICE_PER_1K = {  # (input, output) USD per 1k tokens
    "claude-sonnet-4-6": (0.003, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gemini-2.5-flash": (0.0003, 0.0012),
}


def _estimate(model: str, prompt_chars: int, output_chars: int) -> dict:
    in_tok = prompt_chars // 4
    out_tok = output_chars // 4
    pin, pout = _PRICE_PER_1K.get(model, (0.003, 0.015))
    cost = (in_tok / 1000) * pin + (out_tok / 1000) * pout
    return {"input_tokens": in_tok, "output_tokens": out_tok, "cost_usd": round(cost, 6)}


def _build_task_prompt(original_input: str, node_outputs: dict[str, str]) -> str:
    """Compose a single user turn: the task plus prior agents' work as context.
    Avoids role-alternation pitfalls by never chaining raw assistant turns."""
    if not node_outputs:
        return original_input
    work = "\n\n".join(f"### {nid}\n{out}" for nid, out in node_outputs.items())
    return (
        f"{original_input}\n\n"
        f"---\n## Work completed by other agents so far\n\n{work}\n\n"
        f"---\nContinue the task using the work above where relevant."
    )


async def _new_step(execution_id: str, node_id: str, agent_id, prompt: str) -> uuid.UUID:
    step_id = uuid.uuid4()
    async with get_session_factory()() as db:
        db.add(WorkflowStep(
            id=step_id,
            execution_id=uuid.UUID(execution_id),
            node_id=node_id,
            agent_id=agent_id,
            status="running",
            input={"prompt": prompt},
            started_at=datetime.now(timezone.utc),
        ))
        await db.commit()
    return step_id


async def _finish_step(step_id: uuid.UUID, status: str, output: dict, error: str | None) -> None:
    async with get_session_factory()() as db:
        result = await db.execute(select(WorkflowStep).where(WorkflowStep.id == step_id))
        step = result.scalar_one()
        step.status = status
        step.output = output
        step.error_message = error
        step.completed_at = datetime.now(timezone.utc)
        await db.commit()


async def _run_agent(config: AgentConfig, prompt: str, node_id: str, bus: EventBus) -> str:
    """Drive run_agent_turn, streaming chunks/tool events over the bus, return text."""
    messages = [{"role": "user", "content": prompt}]
    collected: list[str] = []
    async for event in run_agent_turn(
        messages=messages,
        agent_config=config,
        session_id=None, user_id=None, conversation_id=None, cancel_event=None,
    ):
        etype = event.get("type")
        if etype == "chunk":
            collected.append(event["content"])
            await bus.publish("chunk", node_id=node_id, content=event["content"])
        elif etype == "tool_start":
            await bus.publish("tool_start", node_id=node_id,
                              tool_name=event.get("tool_name"), tool_input=event.get("tool_input"))
        elif etype == "tool_end":
            await bus.publish("tool_end", node_id=node_id,
                              tool_name=event.get("tool_name"), tool_result=event.get("tool_result"))
        elif etype == "provider_fallback":
            await bus.publish("provider_fallback", node_id=node_id, to=event.get("to"))
    return "".join(collected)


async def _post_slack_progress(trigger_context: dict | None, message: str) -> None:
    """Post a progress update to the Slack thread if the run was triggered from Slack."""
    if not trigger_context or trigger_context.get("platform") != "slack":
        return
    channel_id = trigger_context.get("channel_id")
    thread_ts = trigger_context.get("thread_ts")
    if not channel_id:
        return
    try:
        from app.services import slack_service
        await slack_service.send_message(channel_id, message, thread_ts=thread_ts)
    except Exception as e:
        logger.warning("Slack progress post failed: %s", e)


def make_agent_node(node_id: str, agent, bus: EventBus, trigger_context: dict | None = None) -> Callable:
    """A worker node: runs the agent on the task + prior work, returns its output."""
    config = AgentConfig.from_db(agent)

    async def node_fn(state: WorkflowState) -> dict:
        prompt = _build_task_prompt(state["original_input"], state.get("node_outputs", {}))
        step_id = await _new_step(state["execution_id"], node_id, agent.id, prompt)
        await bus.publish("node_started", node_id=node_id, label=agent.name, role="agent")

        try:
            output = await _run_agent(config, prompt, node_id, bus)
            usage = _estimate(config.model, len(prompt), len(output))
            await _finish_step(step_id, "completed", {"text": output, "usage": usage}, None)
            await bus.publish("node_completed", node_id=node_id, output=output, usage=usage)
            await _post_slack_progress(trigger_context, f"✅ *{agent.name}* completed")
        except Exception as e:
            logger.exception("Agent node %s failed", node_id)
            await _finish_step(step_id, "failed", {"text": ""}, str(e))
            await bus.publish("node_failed", node_id=node_id, error=str(e))
            output = ""

        new_outputs = dict(state.get("node_outputs", {}))
        new_outputs[node_id] = output
        return {
            "node_outputs": new_outputs,
            "messages": [{"role": "assistant", "content": f"[{node_id}] {output}"}],
        }

    return node_fn


def make_supervisor_node(
    node_id: str, agent, worker_specs: list[dict], bus: EventBus,
    max_iterations: int = 8, end_node_id: str = "end",
    trigger_context: dict | None = None,
) -> Callable:
    """A router node: an LLM decides which worker acts next, or DONE. Writes the
    decision to state['next'], which the conditional edge reads. worker_specs is
    [{"id": node_id, "label": str, "description": str}, ...].

    end_node_id: the actual graph node id for the end node (used in events so the
    UI can mark it as the target instead of the LangGraph sentinel "__end__")."""
    # Supervisor never uses tools — it only decides routing.
    base = AgentConfig.from_db(agent)
    config = AgentConfig(
        name=base.name, system_prompt=base.system_prompt, model=base.model,
        provider=base.provider, temperature=0.0, max_tokens=512, max_iterations=1,
        tools=[], soul_md=base.soul_md, memory_md=base.memory_md,
    )
    roster = "\n".join(f'- "{w["id"]}": {w.get("label", w["id"])} — {w.get("description","")}' for w in worker_specs)

    async def node_fn(state: WorkflowState) -> dict:
        iterations = state.get("iterations", 0) + 1
        await bus.publish("node_started", node_id=node_id, label=agent.name, role="supervisor")

        # Hard stop: never loop forever.
        if iterations > max_iterations:
            await bus.publish("supervisor_decision", node_id=node_id, next=end_node_id,
                              reason="iteration cap reached")
            await bus.publish("node_completed", node_id=node_id, output="")
            return {"next": "__end__", "iterations": iterations}

        work = state.get("node_outputs", {})
        work_summary = "\n\n".join(f"### {k}\n{v}" for k, v in work.items()) or "(no work yet)"
        routing_prompt = (
            f"You are the supervisor of a team of agents. The user's task:\n\n"
            f"{state['original_input']}\n\n"
            f"## Available workers\n{roster}\n\n"
            f"## Work completed so far\n{work_summary}\n\n"
            f"Decide the SINGLE next worker that should act, or reply done if the task "
            f"is fully complete. Respond with ONLY a JSON object, no prose:\n"
            f'{{"next": "<worker_id>" | "done", "reason": "<one short sentence>"}}'
        )

        step_id = await _new_step(state["execution_id"], node_id, agent.id, routing_prompt)
        try:
            raw = await _run_agent(config, routing_prompt, node_id, bus)
            decision = _parse_decision(raw, [w["id"] for w in worker_specs])
            await _finish_step(step_id, "completed", {"text": raw, "decision": decision}, None)
        except Exception as e:
            logger.exception("Supervisor node %s failed", node_id)
            await _finish_step(step_id, "failed", {"text": ""}, str(e))
            decision = {"next": "__end__", "reason": f"supervisor error: {e}"}
            raw = ""

        event_next = end_node_id if decision["next"] == "__end__" else decision["next"]
        await bus.publish("supervisor_decision", node_id=node_id,
                          next=event_next, reason=decision.get("reason", ""))
        await bus.publish("node_completed", node_id=node_id, output=raw)
        await _post_slack_progress(trigger_context, f"🔀 *{agent.name}* routing → *{event_next}*")
        return {"next": decision["next"], "iterations": iterations}

    return node_fn


async def _send_slack_approval_block(
    channel_id: str, thread_ts: str | None, execution_id: str, node_id: str,
    preview: str, label: str
) -> None:
    """Send a Block Kit interactive approval message to Slack."""
    from app.services import slack_service
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "⏸  Approval Required", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{label}*"}},
    ]
    if preview:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"```{preview[:1200]}```"}})
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "block_id": f"approval_{execution_id}_{node_id}",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅  Approve", "emoji": True},
                "style": "primary",
                "action_id": "checkpoint_approve",
                "value": json.dumps({"execution_id": execution_id, "node_id": node_id}),
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "❌  Reject", "emoji": True},
                "style": "danger",
                "action_id": "checkpoint_reject",
                "value": json.dumps({"execution_id": execution_id, "node_id": node_id}),
            },
        ],
    })
    await slack_service.send_blocks(channel_id, blocks, thread_ts=thread_ts)


def make_checkpoint_node(
    node_id: str,
    bus: EventBus,
    approval_mode: str = "web",
    trigger_context: dict | None = None,
    label: str = "Human checkpoint",
    timeout: int = 300,
) -> Callable:
    """Human checkpoint. Blocks on Redis BLPOP until approved/rejected, then
    continues (auto-approves after `timeout` seconds to avoid stalled runs).

    approval_mode:
      'web'   — only the web monitor's Approve/Reject overlay can respond.
      'slack' — also posts the pending output to the Slack thread and accepts
                an 'approve'/'reject' reply there (requires a Slack-triggered run).
      'both'  — web overlay AND Slack reply both work; whichever responds first wins.
    """
    trigger_context = trigger_context or {}

    async def node_fn(state: WorkflowState) -> dict:
        import json
        import redis.asyncio as aioredis
        from app.core.config import settings

        await bus.publish("node_started", node_id=node_id, label=label, role="checkpoint")
        latest = list(state.get("node_outputs", {}).values())
        preview = latest[-1][:1500] if latest else ""
        execution_id = state["execution_id"]
        approval_key = f"approval:{execution_id}:{node_id}"

        # Web monitor overlay (always emitted so the UI can respond).
        await bus.publish("approval_requested", node_id=node_id, preview=preview, mode=approval_mode)

        # Slack approval: post a Block Kit interactive message in-thread so the
        # user can click Approve/Reject buttons. Also register a text-reply mapping
        # as a fallback (the socket worker handles plain-text replies too).
        slack_lookup_key = None
        platform = trigger_context.get("platform")
        if approval_mode in ("slack", "both") and platform == "slack":
            channel_id = trigger_context.get("channel_id")
            thread_ts = trigger_context.get("thread_ts")
            if channel_id and thread_ts:
                from app.services import slack_service
                try:
                    await _send_slack_approval_block(
                        channel_id, thread_ts, execution_id, node_id, preview, label
                    )
                except Exception as e:
                    logger.warning("Slack approval prompt failed: %s", e)
                slack_lookup_key = f"slack_approval:{channel_id}:{thread_ts}"
                r0 = aioredis.from_url(settings.REDIS_URL)
                try:
                    await r0.set(
                        slack_lookup_key,
                        json.dumps({"execution_id": execution_id, "node_id": node_id}),
                        ex=timeout,
                    )
                finally:
                    await r0.aclose()

        # Block until a signal arrives (web button or Slack reply) or timeout.
        r = aioredis.from_url(settings.REDIS_URL)
        try:
            result = await r.blpop(approval_key, timeout=timeout)
            if result:
                data = json.loads(result[1])
                if not data.get("approved", True):
                    reason = data.get("reason", "No reason given")
                    await bus.publish("node_failed", node_id=node_id, error=f"Rejected: {reason}")
                    raise ValueError(f"Checkpoint rejected: {reason}")
        except ValueError:
            raise
        except Exception:
            await bus.publish("approval_timeout", node_id=node_id)
        finally:
            if slack_lookup_key:
                try:
                    await r.delete(slack_lookup_key)
                except Exception:
                    pass
            try:
                await r.aclose()
            except Exception:
                pass

        await bus.publish("node_completed", node_id=node_id, output="(approved)")
        return {}

    return node_fn


def _parse_decision(raw: str, valid_ids: list[str]) -> dict:
    """Extract {"next", "reason"} from the supervisor's reply, tolerating prose
    around the JSON. 'done'/unknown ids map to __end__."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    nxt, reason = "done", ""
    if match:
        try:
            obj = json.loads(match.group(0))
            nxt = str(obj.get("next", "done")).strip()
            reason = str(obj.get("reason", "")).strip()
        except json.JSONDecodeError:
            pass
    if nxt not in valid_ids:
        nxt = "__end__"
    return {"next": nxt, "reason": reason}
