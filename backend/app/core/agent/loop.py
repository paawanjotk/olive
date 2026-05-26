"""
Agentic loop with tool calling and nested observe-me tracing.

Trace tree produced per agent turn:

    agent-turn  (span_type="trace")  ← root
    ├── llm.anthropic  (span_type="generation", sequence=0)
    ├── tool.web_search  (span_type="tool", sequence=1)
    ├── tool.calculator  (span_type="tool", sequence=2)
    └── llm.anthropic  (span_type="generation", sequence=3)  ← final streamed response

If Anthropic fails before yielding any events the entire turn is retried via
the Gemini fallback loop (same tool-calling capability, same event schema).
"""

import asyncio
import json
import logging
from typing import AsyncIterator, Dict, Any, List, Optional

import anthropic

from app.core.config import settings
from app.core.llm.manager import SYSTEM_PROMPT
from app.core.tools import ANTHROPIC_TOOL_DEFS, GEMINI_TOOL_DEFS, execute_tool

logger = logging.getLogger(__name__)

_MAX_TOOL_ROUNDS = 5


def _filtered_anthropic_tools(tool_names: list[str]) -> list:
    """Return only the Anthropic tool defs the agent is allowed to use."""
    if not tool_names:
        return []
    allowed = set(tool_names)
    return [t for t in ANTHROPIC_TOOL_DEFS if t["name"] in allowed]


def _filtered_gemini_tools(tool_names: list[str]):
    """Return a filtered Gemini Tool object or None if nothing matched."""
    if not tool_names or GEMINI_TOOL_DEFS is None:
        return GEMINI_TOOL_DEFS
    try:
        from google.genai import types as gtypes
        allowed = set(tool_names)
        decls = [
            d for d in GEMINI_TOOL_DEFS.function_declarations
            if d.name in allowed
        ]
        return gtypes.Tool(function_declarations=decls) if decls else None
    except Exception:
        return GEMINI_TOOL_DEFS

# ── Per-session provider failure tracking ─────────────────────────────────────
# Maps session_id → {provider_name: consecutive_failure_count}.
# If a provider accumulates ≥ _PROVIDER_FAILURE_THRESHOLD failures within a
# session we skip it and route directly to the next working provider.
_session_provider_failures: Dict[str, Dict[str, int]] = {}
_PROVIDER_FAILURE_THRESHOLD = 2


def _record_failure(session_id: Optional[str], provider: str) -> int:
    """Increment failure count; return the new total."""
    if not session_id:
        return 0
    counts = _session_provider_failures.setdefault(session_id, {})
    counts[provider] = counts.get(provider, 0) + 1
    logger.warning("Provider '%s' failure #%d for session %s", provider, counts[provider], session_id)
    return counts[provider]


def _record_success(session_id: Optional[str], provider: str) -> None:
    """Reset failure count on success so a recovered provider can be retried."""
    if session_id and session_id in _session_provider_failures:
        _session_provider_failures[session_id].pop(provider, None)


def _failures(session_id: Optional[str], provider: str) -> int:
    if not session_id:
        return 0
    return _session_provider_failures.get(session_id, {}).get(provider, 0)


def _msg_preview(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Extract a string preview from the last message, regardless of content type."""
    if not messages:
        return None
    content = messages[-1].get("content", "")
    if isinstance(content, str):
        return content[:200] or None
    return str(content)[:200] or None


# ── Gemini fallback loop ───────────────────────────────────────────────────────

async def _stream_gemini(
    messages: List[Dict[str, Any]],
    cancel_event: Optional[asyncio.Event],
    root_trace: Any,
    obs: Any,
    session_id: Optional[str],
    user_id: Optional[str],
    agent_config: Any = None,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Full agentic loop using Gemini — mirrors the Anthropic loop.

    Yields the same WS event schema:
      {"type": "chunk",      "content": "..."}
      {"type": "tool_start", "tool_name": ..., "tool_input": {...}}
      {"type": "tool_end",   "tool_name": ..., "tool_result": "..."}
    """
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured — cannot use Gemini fallback")
    if GEMINI_TOOL_DEFS is None:
        raise RuntimeError("google-genai not installed — cannot use Gemini fallback")

    from google import genai
    from google.genai import types as gtypes
    from app.core.llm.gemini_provider import _to_gemini_contents

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    contents = _to_gemini_contents(messages)
    _sys_prompt = agent_config.effective_system_prompt if agent_config else SYSTEM_PROMPT
    _max_tok = agent_config.max_tokens if agent_config else settings.GEMINI_MAX_TOKENS
    _gemini_tool = _filtered_gemini_tools(agent_config.tools) if agent_config else GEMINI_TOOL_DEFS
    loop_obj = asyncio.get_running_loop()
    sequence = 0
    _max_rounds = agent_config.max_iterations if agent_config else _MAX_TOOL_ROUNDS

    for _round in range(_max_rounds + 1):
        if cancel_event and cancel_event.is_set():
            return

        # Strip tools on final round to force a synthesis text response
        is_final_round = _round >= _max_rounds
        _round_tool = None if is_final_round else _gemini_tool
        config = gtypes.GenerateContentConfig(
            max_output_tokens=_max_tok,
            system_instruction=_sys_prompt,
            tools=[_round_tool] if _round_tool else [],
        )

        gen_trace = obs.start_trace(
            provider="gemini",
            model=settings.GEMINI_MODEL,
            name="llm.gemini",
            span_type="generation",
            parent_trace_id=root_trace.trace_id if root_trace else None,
            sequence=sequence,
            input_preview=_msg_preview(
                [{"content": p.text} for c in contents
                 for p in (c.parts or []) if p.text]
            ),
            session_id=session_id,
            user_id=user_id,
        ) if obs else None
        sequence += 1

        # Bridge sync Gemini iterator to async via a queue
        queue: asyncio.Queue = asyncio.Queue()

        def _sync_stream(q=queue, cts=list(contents), cfg=config):
            try:
                for chunk in client.models.generate_content_stream(
                    model=settings.GEMINI_MODEL, contents=cts, config=cfg
                ):
                    loop_obj.call_soon_threadsafe(q.put_nowait, ("chunk", chunk))
            except Exception as exc:
                loop_obj.call_soon_threadsafe(q.put_nowait, ("error", exc))
            finally:
                loop_obj.call_soon_threadsafe(q.put_nowait, None)

        loop_obj.run_in_executor(None, _sync_stream)

        text_parts: List[str] = []
        function_calls: List[Any] = []
        cancelled_mid_stream = False
        gemini_prompt_tokens: Optional[int] = None
        gemini_completion_tokens: Optional[int] = None

        while True:
            item = await queue.get()
            if item is None:
                break
            kind, val = item
            if kind == "error":
                if gen_trace:
                    if text_parts:
                        gen_trace._chunks = text_parts
                    gen_trace.fail(val)
                    gen_trace.emit_nowait()
                raise val

            chunk = val
            if cancel_event and cancel_event.is_set():
                cancelled_mid_stream = True
                break

            # Extract token usage from every chunk — the final chunk carries the totals
            usage = getattr(chunk, "usage_metadata", None)
            if usage:
                pt = getattr(usage, "prompt_token_count", None)
                ct = getattr(usage, "candidates_token_count", None)
                if pt:
                    gemini_prompt_tokens = pt
                if ct:
                    gemini_completion_tokens = ct

            # Iterate parts directly — never call chunk.text because the SDK
            # raises ValueError when the chunk contains function_call parts.
            for candidate in (chunk.candidates or []):
                for part in (getattr(candidate.content, "parts", None) or []):
                    fc = getattr(part, "function_call", None)
                    if fc and getattr(fc, "name", None):
                        function_calls.append(fc)
                    else:
                        text = getattr(part, "text", None)
                        if text:
                            text_parts.append(text)
                            yield {"type": "chunk", "content": text}

        if cancelled_mid_stream:
            if gen_trace:
                if text_parts:
                    gen_trace._chunks = text_parts
                gen_trace.cancel()
                gen_trace.emit_nowait()
            if root_trace:
                root_trace.cancel()
            return

        if gen_trace:
            if text_parts:
                gen_trace._chunks = text_parts
            gen_trace.complete(
                prompt_tokens=gemini_prompt_tokens,
                completion_tokens=gemini_completion_tokens,
            )
            gen_trace.emit_nowait()

        if not function_calls:
            break  # end_turn equivalent — text was streamed above

        # ── execute tools then loop ──────────────────────────────────────
        model_parts: List[Any] = []
        result_parts: List[Any] = []

        for fc in function_calls:
            tool_name = fc.name
            tool_input = dict(fc.args) if fc.args else {}

            yield {"type": "tool_start", "tool_name": tool_name, "tool_input": tool_input}

            tool_trace = obs.start_trace(
                provider="tool",
                model=tool_name,
                name=f"tool.{tool_name}",
                span_type="tool",
                parent_trace_id=root_trace.trace_id if root_trace else None,
                sequence=sequence,
                input_preview=str(tool_input)[:200],
                session_id=session_id,
                user_id=user_id,
            ) if obs else None
            sequence += 1

            try:
                result = await execute_tool(tool_name, tool_input)
                if tool_trace:
                    tool_trace._chunks = [result[:200]]
                    tool_trace.complete()
                    tool_trace.emit_nowait()
            except Exception as tool_err:
                result = f"Tool error: {tool_err}"
                if tool_trace:
                    tool_trace._chunks = [result[:200]]
                    tool_trace.fail(tool_err)
                    tool_trace.emit_nowait()

            yield {"type": "tool_end", "tool_name": tool_name, "tool_result": result[:600]}

            model_parts.append(gtypes.Part(function_call=fc))
            result_parts.append(
                gtypes.Part(
                    function_response=gtypes.FunctionResponse(
                        name=tool_name,
                        response={"result": result},
                    )
                )
            )

        contents.append(gtypes.Content(role="model", parts=model_parts))
        contents.append(gtypes.Content(role="user", parts=result_parts))


# ── Public entry-point ─────────────────────────────────────────────────────────

async def run_agent_turn(
    messages: List[Dict[str, Any]],
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    cancel_event: Optional[asyncio.Event] = None,
    agent_config: Optional[Any] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Run one full agent turn (possibly multiple tool calls) and yield WS events.

    Tries Anthropic first. If Anthropic raises before any events are yielded
    (e.g. API key invalid, rate-limit, connectivity), falls back to Gemini
    transparently.

    agent_config: optional AgentConfig dataclass. When None, falls back to the
    default system prompt and all available tools (preserves existing behaviour).
    """
    # ── Resolve agent config ────────────────────────────────────────────────
    from app.core.agent.config import AgentConfig as _AgentConfig
    config = agent_config if agent_config is not None else _AgentConfig.default()

    # ── Observability setup ──────────────────────────────────────────────────
    try:
        import observe_me
        from observe_me.context import _active_trace_id
        obs = observe_me.get_client()
    except ImportError:
        obs = None
        _active_trace_id = None

    # Decide the active provider before creating the root trace so the admin
    # panel shows the model that will actually answer, not the one that failed.
    anthropic_over_threshold = _failures(session_id, "anthropic") >= _PROVIDER_FAILURE_THRESHOLD
    _root_provider = "gemini" if anthropic_over_threshold else "anthropic"
    _root_model    = settings.GEMINI_MODEL if anthropic_over_threshold else settings.ANTHROPIC_MODEL

    root_trace = obs.start_trace(
        provider=_root_provider,
        model=_root_model,
        name="agent-turn",
        span_type="trace",
        session_id=session_id,
        user_id=user_id,
        conversation_id=conversation_id,
        input_preview=messages[-1].get("content", "")[:300] if messages else None,
    ) if obs else None

    _active_tok = None
    if obs and root_trace and _active_trace_id is not None:
        _active_tok = _active_trace_id.set(root_trace.trace_id)

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    current_messages = list(messages)
    sequence = 0
    events_yielded = False  # tracks whether any chunk/tool event reached the caller
    gen_trace = None         # kept in outer scope so fallback handler can emit it

    try:
        # ── Route directly to Gemini when Anthropic is over-threshold ──────
        # Must be inside try/finally so root_trace.emit_nowait() always fires.
        if anthropic_over_threshold:
            logger.info(
                "Anthropic over threshold for session %s — routing silently to Gemini",
                session_id,
            )
            # No provider_fallback nudge here — Gemini is already the established
            # default for this session; there is no live switch to announce.
            try:
                async for event in _stream_gemini(
                    messages, cancel_event, root_trace, obs, session_id, user_id, config
                ):
                    yield event
                _record_success(session_id, "gemini")
            except Exception as gemini_err:
                _record_failure(session_id, "gemini")
                if root_trace:
                    root_trace.fail(gemini_err)
                raise RuntimeError(
                    f"All providers unavailable for this session: {gemini_err}"
                ) from gemini_err
            else:
                if root_trace:
                    root_trace.complete()
            return  # finally still runs after return — root_trace.emit_nowait() fires
        # max_iterations = number of tool-call rounds; the +1 below reserves one
        # final synthesis round where tools are withheld so the LLM must write
        # a text answer rather than calling more tools.
        for _round in range(config.max_iterations + 1):
            if cancel_event and cancel_event.is_set():
                return

            # On the last round, strip tools so the model is forced to synthesise
            # a final text answer from all gathered context instead of looping further.
            is_final_round = _round >= config.max_iterations
            round_tools = [] if is_final_round else _filtered_anthropic_tools(config.tools)

            gen_trace = obs.start_trace(
                provider="anthropic",
                model=settings.ANTHROPIC_MODEL,
                name="llm.anthropic",
                span_type="generation",
                parent_trace_id=root_trace.trace_id if root_trace else None,
                sequence=sequence,
                input_preview=_msg_preview(current_messages),
                session_id=session_id,
                user_id=user_id,
            ) if obs else None
            sequence += 1

            content_blocks: List[Dict[str, Any]] = []
            tool_json_parts: Dict[int, List[str]] = {}
            stop_reason: Optional[str] = None
            cancelled_mid_stream = False

            async with client.messages.stream(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=config.max_tokens,
                system=config.effective_system_prompt,
                tools=round_tools,
                messages=current_messages,
            ) as stream:
                async for event in stream:
                    if cancel_event and cancel_event.is_set():
                        cancelled_mid_stream = True
                        break

                    if event.type == "content_block_start":
                        cb = event.content_block
                        if cb.type == "text":
                            content_blocks.append({"type": "text", "text": ""})
                        elif cb.type == "tool_use":
                            content_blocks.append({
                                "type": "tool_use",
                                "id": cb.id,
                                "name": cb.name,
                                "input": {},
                            })
                            tool_json_parts[event.index] = []

                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            text = delta.text
                            if event.index < len(content_blocks):
                                content_blocks[event.index]["text"] += text
                            events_yielded = True
                            yield {"type": "chunk", "content": text}
                        elif delta.type == "input_json_delta":
                            if event.index in tool_json_parts:
                                tool_json_parts[event.index].append(delta.partial_json)

                    elif event.type == "content_block_stop":
                        idx = event.index
                        if idx in tool_json_parts:
                            try:
                                content_blocks[idx]["input"] = json.loads(
                                    "".join(tool_json_parts[idx])
                                )
                            except Exception:
                                content_blocks[idx]["input"] = {}

                if not cancelled_mid_stream:
                    final_message = await stream.get_final_message()
                    stop_reason = final_message.stop_reason

            if cancelled_mid_stream:
                if gen_trace:
                    partial = [b["text"] for b in content_blocks if b["type"] == "text" and b.get("text")]
                    if partial:
                        gen_trace._chunks = partial
                    gen_trace.cancel()
                    gen_trace.emit_nowait()
                if root_trace:
                    root_trace.cancel()
                return

            # ── Tracing ──────────────────────────────────────────────────
            if gen_trace:
                output_parts: list[str] = []
                for block in content_blocks:
                    if block["type"] == "text" and block.get("text"):
                        output_parts.append(block["text"])
                    elif block["type"] == "tool_use":
                        output_parts.append(
                            f"[tool_use: {block['name']} | input: {str(block.get('input', {}))[:120]}]"
                        )
                if output_parts:
                    gen_trace._chunks = output_parts
                gen_trace.complete(
                    prompt_tokens=final_message.usage.input_tokens,
                    completion_tokens=final_message.usage.output_tokens,
                )
                gen_trace.emit_nowait()

            if stop_reason == "end_turn":
                break

            if stop_reason == "tool_use":
                tool_results: List[Dict[str, Any]] = []

                for block in content_blocks:
                    if block["type"] != "tool_use":
                        continue

                    tool_input = block.get("input", {})

                    events_yielded = True
                    yield {"type": "tool_start", "tool_name": block["name"], "tool_input": tool_input}

                    tool_trace = obs.start_trace(
                        provider="tool",
                        model=block["name"],
                        name=f"tool.{block['name']}",
                        span_type="tool",
                        parent_trace_id=root_trace.trace_id if root_trace else None,
                        sequence=sequence,
                        input_preview=str(tool_input)[:200],
                        session_id=session_id,
                        user_id=user_id,
                    ) if obs else None
                    sequence += 1

                    try:
                        result = await execute_tool(block["name"], tool_input)
                        if tool_trace:
                            tool_trace._chunks = [result[:200]]
                            tool_trace.complete()
                            tool_trace.emit_nowait()
                    except Exception as tool_err:
                        result = f"Tool error: {tool_err}"
                        if tool_trace:
                            tool_trace._chunks = [result[:200]]
                            tool_trace.fail(tool_err)
                            tool_trace.emit_nowait()

                    events_yielded = True
                    yield {"type": "tool_end", "tool_name": block["name"], "tool_result": result[:600]}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": result,
                    })

                current_messages = current_messages + [
                    {"role": "assistant", "content": content_blocks},
                    {"role": "user", "content": tool_results},
                ]
                continue

            logger.warning("Unexpected stop_reason: %s", stop_reason)
            break

        _record_success(session_id, "anthropic")
        if root_trace:
            root_trace.complete()

    except Exception as anthropic_err:
        if events_yielded:
            # Partial stream already sent — can't restart cleanly
            logger.error("Anthropic error mid-stream: %s", anthropic_err, exc_info=True)
            _record_failure(session_id, "anthropic")
            if root_trace:
                root_trace.fail(anthropic_err)
            raise

        # Emit the Anthropic gen_trace as a failed child span so the admin
        # panel shows a separate trace entry for the Anthropic attempt.
        if gen_trace:
            gen_trace.fail(anthropic_err)
            gen_trace.emit_nowait()

        _record_failure(session_id, "anthropic")
        anthropic_reason = str(anthropic_err)
        logger.warning(
            "Anthropic failed before any output (failures so far: %d), falling back to Gemini: %s",
            _failures(session_id, "anthropic"), anthropic_reason,
        )

        # Tell the frontend a provider switch is happening (ephemeral — not persisted)
        yield {
            "type": "provider_fallback",
            "from": "anthropic",
            "to": "gemini",
            "reason": anthropic_reason[:300],
        }

        try:
            async for event in _stream_gemini(
                messages, cancel_event, root_trace, obs, session_id, user_id
            ):
                yield event
            _record_success(session_id, "gemini")
            if root_trace:
                root_trace.complete()
        except Exception as gemini_err:
            _record_failure(session_id, "gemini")
            logger.error("Gemini fallback also failed: %s", gemini_err, exc_info=True)
            if root_trace:
                root_trace.fail(gemini_err)
            raise RuntimeError(
                f"All LLM providers failed. "
                f"Anthropic: {anthropic_reason}. "
                f"Gemini: {gemini_err}"
            ) from gemini_err

    finally:
        if obs and _active_trace_id is not None and _active_tok is not None:
            try:
                _active_trace_id.reset(_active_tok)
            except Exception:
                pass
        if root_trace:
            root_trace.emit_nowait()
