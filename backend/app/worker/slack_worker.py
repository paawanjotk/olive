"""Slack Socket Mode handler.

@mention flow:
  user @mentions bot  →  run_channel_turn("slack", team_id, text)
                      →  full response posted back to thread (typing placeholder first)

Text-reply approval: kept for checkpoint nodes (fallback when Block Kit unavailable).
Block Kit actions: checkpoint_approve / checkpoint_reject for workflow approvals.
"""
import logging

logger = logging.getLogger(__name__)

_handler = None


async def start_socket_handler() -> None:
    """Called from FastAPI lifespan. Exits silently when tokens are missing."""
    try:
        from slack_bolt.async_app import AsyncApp
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    except ImportError as e:
        logger.warning(
            "Slack Socket Mode disabled — import failed (%s). "
            "Ensure 'slack-bolt' and 'aiohttp' are installed.", e
        )
        return

    from app.core.config import settings
    if not settings.SLACK_BOT_TOKEN or not settings.SLACK_APP_TOKEN:
        logger.info("SLACK_BOT_TOKEN / SLACK_APP_TOKEN not set — Slack disabled")
        return

    slack_app = AsyncApp(token=settings.SLACK_BOT_TOKEN)

    # ── Text-reply approval fallback ───────────────────────────────────────────
    @slack_app.event("message")
    async def handle_message(event, say):
        """Only handles approve/reject text replies for pending checkpoint nodes."""
        if event.get("bot_id") or event.get("subtype"):
            return
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts")
        if not channel_id or not thread_ts:
            return

        import json
        import redis.asyncio as aioredis

        lookup_key = f"slack_approval:{channel_id}:{thread_ts}"
        r = aioredis.from_url(settings.REDIS_URL)
        try:
            raw = await r.get(lookup_key)
            if not raw:
                return
            info = json.loads(raw)
            text = (event.get("text") or "").lower()
            if any(w in text for w in ("reject", "deny", "decline", "stop", "cancel", "no")):
                decision = {"approved": False, "reason": event.get("text", "")}
            elif any(w in text for w in ("approve", "approved", "yes", "lgtm", "ok", "go ahead", "proceed")):
                decision = {"approved": True, "reason": event.get("text", "")}
            else:
                await say(text="Reply *approve* to continue or *reject* to stop.", thread_ts=thread_ts)
                return
            approval_key = f"approval:{info['execution_id']}:{info['node_id']}"
            await r.lpush(approval_key, json.dumps(decision))
            await r.delete(lookup_key)
            await say(
                text="✅ Approved — continuing." if decision["approved"] else "🛑 Rejected — stopping.",
                thread_ts=thread_ts,
            )
        finally:
            await r.aclose()

    # ── @mention → direct chat ─────────────────────────────────────────────────
    @slack_app.event("app_mention")
    async def handle_mention(event, say, client):
        from app.services.slack_service import strip_mentions
        from app.core.channel_chat import run_channel_turn_streaming

        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        team_id = event.get("team") or event.get("team_id") or "unknown"
        user_text = strip_mentions(event.get("text", "")).strip() or "Hello!"

        logger.info(
            "Slack @mention: team=%s channel=%s user=%s text=%r",
            team_id, channel_id, event.get("user"), user_text,
        )

        # Post placeholder immediately so users see a response is coming
        typing_ts: str | None = None
        try:
            resp = await client.chat_postMessage(
                channel=channel_id, thread_ts=thread_ts, text="_Thinking…_",
            )
            typing_ts = resp.get("ts")
        except Exception as e:
            logger.warning("Could not post typing placeholder: %s", e)

        async def _update(text: str) -> None:
            if typing_ts:
                try:
                    await client.chat_update(channel=channel_id, ts=typing_ts, text=text)
                except Exception:
                    pass

        # Stream agent events: update the placeholder as tool calls happen
        _TOOL_LABELS = {
            "web_search":          "Searching the web",
            "calculator":          "Calculating",
            "get_datetime":        "Checking the time",
            "list_workflows":      "Fetching workflows",
            "run_workflow":        "Starting workflow",
            "get_workflow_status": "Checking workflow status",
        }

        chunks: list[str] = []
        response = ""
        try:
            async for ev, response_so_far in run_channel_turn_streaming(
                platform="slack",
                external_id=team_id,
                user_text=user_text,
            ):
                if ev.get("type") == "tool_start":
                    label = _TOOL_LABELS.get(ev["tool_name"], f"Using {ev['tool_name']}")
                    await _update(f"_{label}…_")
                elif ev.get("type") == "chunk":
                    chunks.append(ev["content"])
            response = response_so_far
        except Exception as e:
            logger.exception("Agent turn failed for Slack mention: %s", e)
            await _update(f"Sorry, something went wrong: {e}")
            return

        # Final update: full response
        if typing_ts:
            try:
                await client.chat_update(channel=channel_id, ts=typing_ts, text=response or "_(no response)_")
                return
            except Exception as e:
                logger.warning("Final chat_update failed (%s), posting new message", e)
        await say(text=response or "_(no response)_", thread_ts=thread_ts)

    # ── Block Kit approval actions ─────────────────────────────────────────────
    @slack_app.action("checkpoint_approve")
    async def handle_approve_action(ack, body, client):
        await ack()
        try:
            import json
            import redis.asyncio as aioredis
            value = json.loads(body["actions"][0]["value"])
            r = aioredis.from_url(settings.REDIS_URL)
            try:
                await r.lpush(
                    f"approval:{value['execution_id']}:{value['node_id']}",
                    json.dumps({"approved": True, "reason": "Approved via Slack button"}),
                )
                await r.expire(f"approval:{value['execution_id']}:{value['node_id']}", 60)
            finally:
                await r.aclose()
            await client.chat_update(
                channel=body["container"]["channel_id"],
                ts=body["container"]["message_ts"],
                blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "✅ *Approved* — workflow continuing…"}}],
                text="Approved",
            )
        except Exception as e:
            logger.exception("Error handling approve action: %s", e)

    @slack_app.action("checkpoint_reject")
    async def handle_reject_action(ack, body, client):
        await ack()
        try:
            import json
            import redis.asyncio as aioredis
            value = json.loads(body["actions"][0]["value"])
            r = aioredis.from_url(settings.REDIS_URL)
            try:
                await r.lpush(
                    f"approval:{value['execution_id']}:{value['node_id']}",
                    json.dumps({"approved": False, "reason": "Rejected via Slack button"}),
                )
                await r.expire(f"approval:{value['execution_id']}:{value['node_id']}", 60)
            finally:
                await r.aclose()
            await client.chat_update(
                channel=body["container"]["channel_id"],
                ts=body["container"]["message_ts"],
                blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "🛑 *Rejected* — workflow stopped."}}],
                text="Rejected",
            )
        except Exception as e:
            logger.exception("Error handling reject action: %s", e)

    global _handler
    _handler = AsyncSocketModeHandler(slack_app, settings.SLACK_APP_TOKEN)
    logger.info("Starting Slack Socket Mode connection…")
    await _handler.start_async()


async def stop_socket_handler() -> None:
    global _handler
    if _handler is not None:
        try:
            await _handler.close_async()
        except Exception:
            pass
        _handler = None
