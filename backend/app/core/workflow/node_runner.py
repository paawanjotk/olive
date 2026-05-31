"""LangGraph node factories. Each factory returns an async node function that
LangGraph calls with the shared WorkflowState. Nodes run agents via the existing
run_agent_turn loop, persist a workflow_steps row, stream chunks over the event
bus, and return a state delta."""
import asyncio
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


async def _persist_event(execution_id: str, step_id: uuid.UUID, event_type: str, payload: dict) -> None:
    """Fire-and-forget: write one event row to execution_events for trace history."""
    try:
        from app.db.models.workflows import ExecutionEvent
        async with get_session_factory()() as db:
            db.add(ExecutionEvent(
                execution_id=uuid.UUID(execution_id),
                step_id=step_id,
                event_type=event_type,
                payload=payload,
            ))
            await db.commit()
    except Exception:
        pass  # telemetry must never kill the run


async def _run_agent(
    config: AgentConfig, prompt: str, node_id: str, bus: EventBus,
    cancel_event: asyncio.Event | None = None,
    execution_id: str | None = None,
    trigger_context: dict | None = None,
    step_id: uuid.UUID | None = None,
    user_id: str | None = None,
) -> str:
    """Drive run_agent_turn, streaming chunks/tool events over the bus, return text."""
    messages = [{"role": "user", "content": prompt}]
    collected: list[str] = []
    async for event in run_agent_turn(
        messages=messages,
        agent_config=config,
        session_id=None, user_id=user_id, conversation_id=None, cancel_event=cancel_event,
        execution_id=execution_id, trigger_context=trigger_context,
    ):
        etype = event.get("type")
        if etype == "chunk":
            # Collect BEFORE checking cancel so no text is silently dropped
            # if the watcher sets cancel_event mid-synthesis-stream.
            collected.append(event["content"])
            await bus.publish("chunk", node_id=node_id, content=event["content"])
        elif etype == "tool_start":
            await bus.publish("tool_start", node_id=node_id,
                              tool_name=event.get("tool_name"), tool_input=event.get("tool_input"))
            if execution_id and step_id:
                asyncio.create_task(_persist_event(execution_id, step_id, "tool_start", {
                    "tool_name": event.get("tool_name", ""),
                    "tool_input": event.get("tool_input") or {},
                }))
        elif etype == "tool_approval_requested":
            await bus.publish("tool_approval_requested", node_id=node_id,
                              tool_name=event.get("tool_name"),
                              tool_input=event.get("tool_input"),
                              call_id=event.get("call_id"))
        elif etype == "tool_end":
            await bus.publish("tool_end", node_id=node_id,
                              tool_name=event.get("tool_name"), tool_result=event.get("tool_result"))
            if execution_id and step_id:
                result_raw = event.get("tool_result", "")
                asyncio.create_task(_persist_event(execution_id, step_id, "tool_end", {
                    "tool_name": event.get("tool_name", ""),
                    "tool_result": str(result_raw)[:5000],
                }))
        elif etype == "provider_fallback":
            await bus.publish("provider_fallback", node_id=node_id, to=event.get("to"))
        if cancel_event and cancel_event.is_set():
            break  # break AFTER processing so the last chunk/event isn't lost
    return "".join(collected)


async def _post_slack_progress(trigger_context: dict | None, message: str) -> None:
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


async def _check_control(execution_id: str, node_id: str, bus: EventBus) -> None:
    """Raise PauseSignal or TerminateSignal if a control signal is pending."""
    from app.services.execution_control import get_signal, PauseSignal, TerminateSignal
    signal = await get_signal(execution_id)
    if signal == "terminate":
        await bus.publish("node_failed", node_id=node_id, error="Terminated by user")
        raise TerminateSignal()
    if signal == "pause":
        await bus.publish("node_failed", node_id=node_id, error="Paused by user")
        raise PauseSignal()


async def _run_with_retry(
    fn, node_id: str, bus: EventBus, max_retries: int = 1
) -> str:
    """Run fn() with exponential-backoff retry. PauseSignal/TerminateSignal always propagate."""
    import asyncio
    from app.services.execution_control import PauseSignal, TerminateSignal
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except (PauseSignal, TerminateSignal):
            raise  # never retry on control signals
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                delay = 2.0 * (2 ** attempt)
                logger.warning("Node %s failed (attempt %d/%d), retrying in %.1fs: %s",
                               node_id, attempt + 1, max_retries + 1, delay, e)
                await bus.publish("tool_start", node_id=node_id,
                                  tool_name="retry", tool_input={"attempt": attempt + 1, "delay": delay})
                await asyncio.sleep(delay)
                await bus.publish("tool_end", node_id=node_id,
                                  tool_name="retry", tool_result=f"Retrying (attempt {attempt + 2})")
    raise last_exc  # type: ignore[misc]


def _apply_node_overrides(base_config: AgentConfig, node_data: dict) -> AgentConfig:
    """Merge per-node config overrides (from graph_json node.data) onto the base agent config."""
    from dataclasses import replace
    overrides: dict = {}
    for field, key in [
        ("system_prompt", "system_prompt"),
        ("model", "model"),
        ("provider", "provider"),
        ("temperature", "temperature"),
        ("max_tokens", "max_tokens"),
        ("max_iterations", "max_iterations"),
        ("soul_md", "soul_md"),
        ("memory_md", "memory_md"),
        ("tool_approval_mode", "tool_approval_mode"),
        ("tool_approval_timeout", "tool_approval_timeout"),
    ]:
        val = node_data.get(key)
        if val is not None and val != "":
            overrides[field] = val
    # tools override: only apply if the list is non-empty in node_data
    tools = node_data.get("tools")
    if isinstance(tools, list) and tools:
        overrides["tools"] = tools
    # approval_tools override
    approval_tools = node_data.get("approval_tools")
    if isinstance(approval_tools, list):
        overrides["approval_tools"] = approval_tools
    # mcp_providers override: explicit list in node_data wins over agent default
    mcp_providers = node_data.get("mcp_providers")
    if isinstance(mcp_providers, list):
        overrides["mcp_providers"] = mcp_providers
    return replace(base_config, **overrides) if overrides else base_config


def make_agent_node(
    node_id: str, agent, bus: EventBus,
    trigger_context: dict | None = None,
    node_data: dict | None = None,
    max_retries: int = 1,
) -> Callable:
    """A worker node: runs the agent on the task + prior work, returns its output.

    node_data: the graph_json node.data dict — allows per-node config overrides
    (system_prompt, model, tools, temperature, etc.) on top of the base agent.
    max_retries: automatic retry count on transient failures (default=1).
    """
    base_config = AgentConfig.from_db(agent)
    config = _apply_node_overrides(base_config, node_data or {})

    from app.services.execution_control import PauseSignal, TerminateSignal

    async def node_fn(state: WorkflowState) -> dict:
        execution_id = state["execution_id"]

        # Upfront control check (catches signals set before the node starts)
        await _check_control(execution_id, node_id, bus)

        current_outputs: dict[str, str] = dict(state.get("node_outputs") or {})
        prompt = _build_task_prompt(state["original_input"], current_outputs)
        step_id = await _new_step(execution_id, node_id, agent.id, prompt)
        await bus.publish("node_started", node_id=node_id, label=agent.name, role="agent")

        # Background poller: sets cancel_event as soon as a Redis signal appears.
        # This makes pause/terminate responsive mid-LLM-call (~1 s latency).
        cancel_event = asyncio.Event()

        async def _watch_signal() -> None:
            from app.services.execution_control import get_signal
            while not cancel_event.is_set():
                await asyncio.sleep(1)
                if await get_signal(execution_id):
                    cancel_event.set()

        watcher = asyncio.create_task(_watch_signal())

        _user_id = str(agent.user_id) if getattr(agent, "user_id", None) else None
        try:
            output = await _run_with_retry(
                lambda: _run_agent(config, prompt, node_id, bus, cancel_event,
                                   execution_id=execution_id, trigger_context=trigger_context,
                                   step_id=step_id, user_id=_user_id),
                node_id=node_id, bus=bus, max_retries=max_retries,
            )
            # If the watcher set cancel_event during the run, raise the right signal now.
            if cancel_event.is_set():
                await _check_control(execution_id, node_id, bus)

            usage = _estimate(config.model, len(prompt), len(output))
            await _finish_step(step_id, "completed", {"text": output, "usage": usage}, None)
            await bus.publish("node_completed", node_id=node_id, output=output, usage=usage)
            await _post_slack_progress(trigger_context, f"✅ *{agent.name}* completed")
        except (PauseSignal, TerminateSignal):
            await _finish_step(step_id, "failed", {"text": ""}, "Execution paused/terminated")
            raise
        except Exception as e:
            logger.exception("Agent node %s failed after retries", node_id)
            await _finish_step(step_id, "failed", {"text": ""}, str(e))
            await bus.publish("node_failed", node_id=node_id, error=str(e))
            output = ""
        finally:
            cancel_event.set()  # stop the watcher regardless of outcome
            watcher.cancel()

        # Accumulate: when supervisor routes to the same node multiple times,
        # append each run so the supervisor sees the full body of work.
        prev = current_outputs.get(node_id, "")
        new_outputs = dict(current_outputs)
        if prev and output:
            new_outputs[node_id] = prev + "\n\n" + output
        else:
            new_outputs[node_id] = output or prev
        return {
            "node_outputs": new_outputs,
            "messages": [{"role": "assistant", "content": f"[{node_id}] {output}"}],
        }

    return node_fn


def make_supervisor_node(
    node_id: str, agent, worker_specs: list[dict], bus: EventBus,
    max_iterations: int = 8, end_node_id: str = "end",
    trigger_context: dict | None = None,
    node_data: dict | None = None,
) -> Callable:
    """A router node: an LLM decides which worker acts next, or DONE. Writes the
    decision to state['next'], which the conditional edge reads. worker_specs is
    [{"id": node_id, "label": str, "description": str}, ...].

    end_node_id: the actual graph node id for the end node (used in events so the
    UI can mark it as the target instead of the LangGraph sentinel "__end__")."""
    from app.services.execution_control import PauseSignal, TerminateSignal
    base = _apply_node_overrides(AgentConfig.from_db(agent), node_data or {})
    # Supervisor never uses tools — it only decides routing.
    config = AgentConfig(
        name=base.name, system_prompt=base.system_prompt, model=base.model,
        provider=base.provider, temperature=0.0, max_tokens=512, max_iterations=1,
        tools=[], soul_md=base.soul_md, memory_md=base.memory_md,
    )
    roster = "\n".join(f'- "{w["id"]}": {w.get("label", w["id"])} — {w.get("description","")}' for w in worker_specs)

    async def node_fn(state: WorkflowState) -> dict:
        execution_id = state["execution_id"]

        # Control signal check before doing any work
        await _check_control(execution_id, node_id, bus)

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
        # Identify checkpoint nodes so the supervisor knows not to re-visit them.
        checkpoint_ids = [w["id"] for w in worker_specs if w.get("kind") == "checkpoint"]
        checkpoint_note = ""
        if checkpoint_ids:
            checkpoint_note = (
                "\n\nIMPORTANT: Nodes marked [checkpoint] are one-time human-approval gates. "
                "If a checkpoint appears in 'Work completed so far' with value 'checkpoint:approved', "
                "it has already been passed — do NOT route to it again. Route to the next logical worker."
            )
        routing_prompt = (
            f"You are the supervisor of a team of agents. The user's task:\n\n"
            f"{state['original_input']}\n\n"
            f"## Available workers\n{roster}{checkpoint_note}\n\n"
            f"## Work completed so far\n{work_summary}\n\n"
            f"Decide the SINGLE next worker that should act, or reply done if the task "
            f"is fully complete. Respond with ONLY a JSON object, no prose:\n"
            f'{{"next": "<worker_id>" | "done", "reason": "<one short sentence>"}}'
        )

        _sup_user_id = str(agent.user_id) if getattr(agent, "user_id", None) else None
        step_id = await _new_step(execution_id, node_id, agent.id, routing_prompt)
        try:
            raw = await _run_agent(config, routing_prompt, node_id, bus, user_id=_sup_user_id)
            decision = _parse_decision(raw, [w["id"] for w in worker_specs])
            await _finish_step(step_id, "completed", {"text": raw, "decision": decision}, None)
        except (PauseSignal, TerminateSignal):
            await _finish_step(step_id, "failed", {"text": ""}, "Execution control signal")
            raise
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
    slack_channel_id: str | None = None,
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

        # Control signal check before blocking on approval
        await _check_control(state["execution_id"], node_id, bus)

        execution_id = state["execution_id"]
        latest = list(state.get("node_outputs", {}).values())
        preview = latest[-1][:1500] if latest else ""

        # Create a WorkflowStep row so the checkpoint appears in the trace like every other node.
        step_id = await _new_step(execution_id, node_id, None, preview or "(awaiting approval)")

        await bus.publish("node_started", node_id=node_id, label=label, role="checkpoint")
        approval_key = f"approval:{execution_id}:{node_id}"

        # Web monitor overlay — only emitted when the mode calls for web interaction.
        # "slack" mode must NOT show the web overlay: it would let the UI approve
        # while Slack is still waiting, creating a race/duplicate-approval situation.
        if approval_mode in ("web", "both"):
            await bus.publish("approval_requested", node_id=node_id, preview=preview, mode=approval_mode)
        else:
            # Still log it in the event stream so the monitor shows "awaiting approval"
            # as a status line, but without opening the interactive overlay.
            await bus.publish("approval_requested_slack", node_id=node_id, preview=preview, mode=approval_mode)

        # Slack approval: post a Block Kit interactive message so the user can
        # click Approve/Reject. Works whether the workflow was triggered from Slack
        # or manually — as long as a channel is known.
        #
        # Channel resolution priority:
        #   1. slack_channel_id configured directly on the checkpoint node (node_data)
        #   2. channel_id from trigger_context (when triggered from Slack)
        slack_lookup_key = None
        if approval_mode in ("slack", "both"):
            channel_id = slack_channel_id or (trigger_context.get("channel_id") if trigger_context else None)
            thread_ts = trigger_context.get("thread_ts") if trigger_context else None
            if channel_id:
                try:
                    await _send_slack_approval_block(
                        channel_id, thread_ts, execution_id, node_id, preview, label
                    )
                except Exception as e:
                    logger.warning("Slack approval prompt failed: %s", e)
                # Register text-reply lookup key (socket worker uses this for plain-text replies).
                slack_lookup_key = f"slack_approval:{channel_id}:{thread_ts or 'direct'}"
                r0 = aioredis.from_url(settings.REDIS_URL)
                try:
                    await r0.set(
                        slack_lookup_key,
                        json.dumps({"execution_id": execution_id, "node_id": node_id}),
                        ex=timeout,
                    )
                finally:
                    await r0.aclose()
            else:
                logger.warning(
                    "Checkpoint %s: approval_mode=%s but no Slack channel configured. "
                    "Set 'Slack channel ID' on the checkpoint node in the workflow builder.",
                    node_id, approval_mode,
                )

        # Block until a signal arrives (web button or Slack reply) or timeout.
        r = aioredis.from_url(settings.REDIS_URL)
        approved = True
        reject_reason = ""
        try:
            result = await r.blpop(approval_key, timeout=timeout)
            if result:
                data = json.loads(result[1])
                if not data.get("approved", True):
                    approved = False
                    reject_reason = data.get("reason", "No reason given")
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

        if not approved:
            await _finish_step(step_id, "failed", {"text": f"Rejected: {reject_reason}"}, reject_reason)
            await bus.publish("node_failed", node_id=node_id, error=f"Rejected: {reject_reason}")
            raise ValueError(f"Checkpoint rejected: {reject_reason}")

        await _finish_step(step_id, "completed",
                           {"text": "approved", "approval_mode": approval_mode}, None)
        await bus.publish("node_completed", node_id=node_id, output="(approved)")
        # Write to node_outputs so the supervisor sees this checkpoint as completed
        # and does NOT route back to it on the next turn.
        new_outputs = dict(state.get("node_outputs") or {})
        new_outputs[node_id] = "checkpoint:approved"
        return {"node_outputs": new_outputs}

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
