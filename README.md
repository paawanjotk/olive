# Ollive — AI Agent Orchestration Platform

Build AI agents as living personas, compose them on a visual canvas into collaborative
multi-agent workflows, watch them work in real time, and talk to them on Telegram.

Submission for the **Yuno AI Engineer Hiring Challenge — AI Agent Orchestration Platform**.

---

## What it does

- **Agent studio** — create agents with a persona (`SOUL.md`), durable memory (`MEMORY.md`),
  a model/temperature/tool set (its "brain"), and guardrails. (openclaw-inspired identity model.)
- **Visual workflow builder** — a React Flow canvas where you drop agent / supervisor /
  checkpoint nodes and wire them together. **Solid edges** are deterministic; **dotted edges**
  are agent-decided (a supervisor routes at runtime).
- **Real multi-agent runtime** — workflows run on **LangGraph** inside a **Celery** worker.
  A supervisor agent reads the shared state and decides which specialist acts next, looping
  with feedback until the task is done.
- **Live monitoring** — a Server-Sent-Events stream lights up nodes as they run, animates the
  edges the supervisor actually fires, streams each agent's tokens, and tracks token/cost per step.
- **Blocking human-in-the-loop** — a **Checkpoint node** pauses the entire execution until a
  human approves or rejects. Approval can come from the **Monitoring dashboard** (web Approve/Reject
  buttons) or — for the full demo path — directly from **Slack Block Kit interactive buttons**.
  The worker subscribes to a Redis key and unblocks immediately on receipt.
- **Slack integration** — mention the bot in a channel to trigger a workflow; the worker posts
  progress updates to the thread and sends an interactive Block Kit card when approval is needed.
  Clicking *Approve* or *Reject* in Slack resumes execution in under a second.
- **Telegram channel** — any workflow can be bound to a Telegram chat. Inbound messages run the
  workflow through the *same* engine and the result is delivered back to the chat.
- **Live monitoring dashboard** — built into the frontend (Activity tab): running/completed/failed
  stats, per-execution node timeline, live SSE token-stream, and inline approval controls.
- **Four prebuilt templates** — *Research Report* (researcher ⇄ writer loop), *Support Triage*
  (routes to billing/technical/general + a human-approval checkpoint, Telegram-ready),
  *Slack Thread Summarizer* (summarises a Slack thread on @mention), and
  *Slack Q&A Assistant* (answers questions with web search + mandatory approval gate).
- **Scheduled workflows** — Celery Beat `check_due_schedules` fires due schedules every 60 s;
  supports one-time and repeating (every N minutes) triggers. Full CRUD API under `/workflows/{id}/schedules`.

---

## Architecture

```
┌───────────────────────────── Frontend (Next.js) ──────────────────────────────┐
│  Agent Studio        Workflow Builder (React Flow)      Live Monitor (SSE)      │
│  SOUL / MEMORY /     solid = deterministic              nodes light up,         │
│  tools / guardrails  dotted = agent-decided             edges fire, tokens/cost │
└───────────┬───────────────────────────────────────────────────▲────────────────┘
            │ REST + WebSocket(chat)                              │ SSE
            ▼                                                     │
┌──────────────────────────── FastAPI backend ──────────────────┴────────────────┐
│ /agents  /workflows  /channels  /webhooks/telegram  /workflows/.../stream        │
│ Supabase JWT auth (ES256 via JWKS) · per-user isolation on every row             │
└───────────┬─────────────────────────────────────────────┬──────────────────────┘
            │ enqueue execution                            │ publish events
            ▼                                               ▲
┌────────────────────────┐   pub/sub    ┌──────────────────┴───────────┐
│   Celery worker         │ ───────────▶ │            Redis              │
│   LangGraph StateGraph  │              │  broker + result + pub/sub    │
│   runs here (1 task /   │ ◀─────────── │                               │
│   execution). Supervisor│   broker     └───────────────────────────────┘
│   routing + tool calls. │
└───────────┬─────────────┘
            │ read agents / write steps + status
            ▼
┌──────────────────────────── PostgreSQL ─────────────────────────────────────────┐
│ users · agents · workflows · workflow_executions · workflow_steps                │
│ execution_events · channel_bindings · sessions · conversations                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### How a workflow runs (the important part)

1. `POST /workflows/{id}/execute` creates a `workflow_executions` row and enqueues **one**
   Celery task (`execute_workflow`). The task id is stored for cancellation/monitoring.
2. The worker loads the blueprint (`graph_json`), resolves each node's agent, and compiles a
   **LangGraph `StateGraph`**. Agent/supervisor/checkpoint nodes become graph nodes.
3. LangGraph walks the graph. A **supervisor node** is an LLM call that returns
   `{"next": "<worker>" | "done"}`; a conditional edge routes to that worker. Workers run via the
   existing agent loop (`run_agent_turn`) — real tool calls, real streaming. Each node writes a
   `workflow_steps` row and publishes events to Redis.
4. The FastAPI **SSE endpoint** subscribes to `workflow:{execution_id}` and relays events to the
   browser. If the run was triggered from Telegram, the worker also sends the final output back
   to the chat.

**Why one Celery task per execution, not per node?** Nodes in a supervised workflow run
sequentially with shared state — LangGraph handles routing in-process. Splitting each node into
its own task would add coordination overhead and race conditions for zero benefit. Truly parallel
autonomous "swarms" are a separate mode (see Roadmap).

---

## Runtime choice — why LangGraph (+ openclaw identity)

| Option | Verdict |
|--------|---------|
| **LangGraph** ✅ | Its data model **is** a node-and-edge graph, so it maps 1:1 onto the visual canvas. Routing is configurable per edge (LLM-decided *or* rule-based), and state is explicit/inspectable — ideal for live monitoring and replay. |
| CrewAI | Role/goal/backstory is a nice config schema (borrowed for agent fields), but hierarchical delegation is a black box — hard to visualize or control. |
| AutoGen | Great emergent group chat, but routing is buried in a transcript with no clean visual primitive. |

The **agent identity model is inspired by openclaw**: a `SOUL.md` persona and a `MEMORY.md`
durable-memory file are merged into the system prompt, and channels bind to agents/workflows.
This gives the "agent-as-a-living-persona" feel the challenge calls out, on top of LangGraph's
orchestration.

**Stack:** Python/FastAPI (async, strong typing), PostgreSQL + SQLAlchemy, Redis + Celery,
Next.js 14 + React Flow + Tailwind, Supabase auth (Google OAuth, ES256 JWT verified via JWKS).

---

## Run it locally

### Prerequisites
- Docker + Docker Compose
- Node 18+ and `pnpm`
- An Anthropic API key (Gemini/OpenAI optional fallbacks), a Tavily key (for `web_search`),
  a Supabase project (Google OAuth enabled), and — for the messaging demo — a Telegram bot token.

### 1. Backend (one command)

```bash
cd backend
cp .env.example .env   # then fill in the keys below
docker compose up --build
```

This starts **db, redis, backend, worker**. Migrations run automatically on boot.
API at `http://localhost:8000` (docs at `/docs`).

`backend/.env` — minimum keys for a working local stack:
```
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...             # powers web_search tool
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=...
# Optional channels:
TELEGRAM_BOT_TOKEN=                 # from @BotFather
TELEGRAM_WEBHOOK_SECRET=            # any random string
SLACK_BOT_TOKEN=xoxb-...            # Bot User OAuth Token
SLACK_APP_TOKEN=xapp-...            # Socket Mode App-level Token
```

### 2. Frontend

```bash
cd frontend
pnpm install
pnpm dev      # http://localhost:3000
```

`frontend/.env`:
```
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_BACKEND_HTTP_URL=http://localhost:8000
```

### 3. Try it
1. Sign in with Google at `http://localhost:3000`.
2. Go to **Workflows → Use template → Research Report**. The builder opens with the agents wired up.
3. Click **Run**, type a task ("3 key trends in AI agent frameworks, briefly"), and watch the
   live monitor: the supervisor routes to the researcher, then the writer, then ends.

---

## Connect Slack (Block Kit approval demo)

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps).
2. Under **OAuth & Permissions**, add bot scopes: `chat:write`, `commands`, `app_mentions:read`.
3. Under **Socket Mode**, enable it and generate an **App-level token** (`xapp-...`). This is `SLACK_APP_TOKEN`.
4. Install the app to your workspace; copy the **Bot User OAuth Token** (`xoxb-...`). This is `SLACK_BOT_TOKEN`.
5. Under **Interactivity & Shortcuts**, enable Interactivity (required for Block Kit button callbacks).
   The request URL can point anywhere — Socket Mode handles it, not HTTP.
6. Put both tokens in `backend/.env`, restart with `docker compose up`.
7. Invite the bot to a channel (`/invite @YourBot`), then @mention it:
   ```
   @YourBot what are the 3 key AI trends in 2025?
   ```
8. The bot immediately replies *"Thinking…"*, runs the full agent turn (same loop as the web chat,
   with tool calls if needed), then replaces the placeholder with the complete answer.
9. **Thread context**: the bot reads the entire Slack thread on every message — so you can have a
   back-and-forth conversation entirely in Slack with full history.
10. **To trigger a workflow with approval**: use the chat interface or `run_workflow` via the agent.
    Block Kit Approve/Reject buttons still work for checkpoint nodes when workflows are triggered
    from the web UI or programmatically.

---

## Connect an agent to Telegram

1. Create a bot with [@BotFather](https://t.me/BotFather) → put the token in `TELEGRAM_BOT_TOKEN`, restart backend.
2. Expose the backend publicly (e.g. `cloudflared tunnel --url http://localhost:8000` or `ngrok http 8000`).
3. Register the webhook (authenticated; use the in-app helper or curl):
   `POST /api/v1/channels/telegram/set-webhook` with `{ "webhook_url": "https://<public>/api/v1/webhooks/telegram" }`.
4. Message your bot, note your chat id, and in **Workflows → Telegram channels** bind that chat id
   to the **Support Triage** workflow.
5. Send the bot a message ("I was double-charged this month") — the supervisor routes it to the
   Billing specialist, hits the approval checkpoint, and replies in the chat.

---

## Project layout

```
backend/
  app/core/workflow/    # state, graph_builder, node_runner, executor, templates, events
  app/worker/           # Celery app + execute_workflow task
  app/db/models/        # agents, workflows, channels, ...
  app/api/v1/endpoints/ # agents, workflows, channels, webhooks, chat, auth
  app/services/         # workflow_service, telegram_service, agent_service
frontend/
  components/workflows/ # WorkflowsPanel, WorkflowBuilder, ExecutionMonitor, WorkflowNodes
  components/agents/    # AgentForm (Identity/Brain/Memory/Channels/Guardrails), ...
  hooks/useExecutionStream.ts   # SSE → live state reducer
  lib/workflowGraph.ts          # graph_json <-> React Flow + edge styling
```

## Extending

- **Add a workflow template:** append an entry to `backend/app/core/workflow/templates.py`
  (its agents + a `build_graph()` returning React Flow `{nodes, edges}`). It appears automatically
  under *Workflows → templates*.
- **Add a messaging channel:** add a sibling of `telegram_service.py` with the same
  `send_message` contract and a webhook endpoint; the engine stays channel-agnostic via
  `workflow_executions.trigger_context`.
- **Add a tool:** register it in `backend/app/core/tools` and add it to `AVAILABLE_TOOLS`; it
  becomes selectable per agent.

---

## Tests

Seven integration tests in `backend/tests/test_critical_paths.py` cover the three spec-required
critical paths: agent CRUD, workflow execution lifecycle, and message delivery (Telegram + Slack +
Block Kit). They run against an in-memory SQLite database with all external services mocked —
no network calls, no Postgres needed.

```bash
# Inside the running container:
docker compose exec backend pytest tests/ -q

# Or with poetry directly (needs aiosqlite installed):
cd backend && poetry run pytest tests/ -q
```

---

## Roadmap (deliberately not built, given the timebox)

- **Parallel agent swarms** — per-agent Celery tasks pulling from a shared queue for true
  concurrent autonomous agents (current engine is one task per execution, sequential/looping).
- **Vector memory** — pgvector-backed semantic recall on top of `MEMORY.md` (today memory is the
  full file injected into the prompt).
- **WhatsApp channel** — Twilio adapter following the same `send_message` contract as Telegram/Slack.
- **Cost guardrails enforcement** — the `max_cost_usd` guardrail field is persisted but not yet
  enforced mid-run (needs token-count tracking piped back to the supervisor).
- **Memory write-back** — currently `MEMORY.md` is injected into the system prompt at run start
  but not updated after a run; a post-run summarise-and-patch step would give true durable learning.
