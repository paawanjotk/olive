# Ollive — AI Agent Orchestration Platform

**Yuno AI Engineer Hiring Challenge submission.**

Users create AI agents as living personas, wire them into collaborative multi-agent workflows on a visual canvas, and watch them execute in real time. Any workflow can be triggered from Telegram or Slack — a human can have a full conversation with the system through either channel.

---

## Evaluation criteria checklist

| Criterion | Status |
|---|---|
| Working end-to-end demo (2+ agents, real tool calls) | ✅ 4 prebuilt templates, runs locally |
| Agent CRUD: name, role, system prompt, model, tools, channels | ✅ Full CRUD with guardrails |
| Agent configuration: schedules, memory, skills, interaction rules, guardrails | ✅ All fields persisted |
| Visual workflow builder with conditions and feedback loops | ✅ React Flow canvas, solid/dotted edges |
| At least 2 prebuilt workflow templates | ✅ 4 templates |
| External channel integration (Telegram + Slack) | ✅ Both |
| Live monitoring: real-time logs, inter-agent messages, token/cost tracking | ✅ SSE stream |
| Tests for critical paths: agent creation, workflow execution, message delivery | ✅ 19/19 passing |
| README: architecture diagram, setup, runtime justification, extension instructions | ✅ This document |

---

## Architecture

```
┌──────────────────────────── Frontend (Next.js 14) ────────────────────────────┐
│  Agent Studio          Workflow Builder (React Flow)    Live Monitor (SSE)      │
│  SOUL.md / MEMORY.md   solid edge = deterministic       nodes light up,         │
│  tools / guardrails    dotted edge = agent-decided      edges animate on fire   │
│  schedules / channels  drag-and-drop, 4 templates       token/cost per step     │
└──────────┬────────────────────────────────────────────────────▲────────────────┘
           │ REST + WebSocket (chat)                             │ SSE events
           ▼                                                     │
┌──────────────────────────── FastAPI backend ──────────────────┴────────────────┐
│  /api/v1/agents   /workflows   /channels   /webhooks/telegram                   │
│  /webhooks/slack  /chat        /sessions   /workflows/{id}/stream               │
│  Supabase JWT auth (ES256 via JWKS) — per-user row isolation on every query     │
└──────────┬────────────────────────────────────────┬───────────────────────────┘
           │ enqueue task                            │ publish step events
           ▼                                         ▲
┌──────────────────────┐   Redis pub/sub  ┌──────────┴─────────────┐
│  Celery worker        │ ──────────────▶ │         Redis           │
│  LangGraph StateGraph │                 │  broker + result store  │
│  1 task / execution   │ ◀────────────── │  + workflow event bus   │
│  supervisor routing   │   Celery broker └────────────────────────┘
│  real tool calls      │
└──────────┬────────────┘
           │ read agents / write steps + status
           ▼
┌────────────────────────── PostgreSQL ─────────────────────────────────────────┐
│  users · agents · workflows · workflow_executions · workflow_steps             │
│  execution_events · channel_bindings · sessions · conversations                │
└───────────────────────────────────────────────────────────────────────────────┘
```

### How a workflow executes — step by step

1. `POST /workflows/{id}/execute` creates a `workflow_executions` row and enqueues **one** Celery task (`execute_workflow`). One task per execution — not per node — because LangGraph routes internally and splitting per-node adds coordination overhead with zero benefit.
2. The worker loads the stored `graph_json`, resolves each node's agent from the DB, and compiles a **LangGraph `StateGraph`** in memory.
3. LangGraph walks the graph. A **supervisor node** makes an LLM call that returns `{"next": "<worker>"|"done"}`. A `conditional_edge` routes to that worker. Worker nodes call `run_agent_turn` — real tool calls, real token streaming. Each node writes a `workflow_steps` row and publishes step/chunk events to Redis.
4. The FastAPI **SSE endpoint** subscribes to `workflow:{execution_id}` on Redis and relays events to the browser. The React Flow canvas highlights each node and edge as it fires.
5. If the workflow was triggered from Telegram or Slack, the worker sends the final output back to that channel.

### The canvas is a possibility space, not a script

The user draws the *boundaries of autonomy* — which agents exist, what tools they have, which delegations are allowed. The supervisor picks a path through this space at runtime. Solid edges on the canvas = deterministic routes. Dotted edges = agent-decided routes.

---

## Runtime choice — why LangGraph + openclaw identity

### Framework decision

| Option | Assessment |
|---|---|
| **LangGraph** ✅ | Its data model **is** a node-and-edge graph, mapping 1:1 onto the visual canvas. Routing is configurable per edge — deterministic OR LLM-decided. State is explicit and inspectable, ideal for live monitoring and replay. Backward edges (feedback loops) are supported natively. |
| CrewAI | Role/goal/backstory is a clean config schema but hierarchical delegation is a black box — no visual primitive, no per-edge routing control. |
| AutoGen | Good emergent group chat but routing is buried in a transcript with no clean graph primitive to display. |
| Custom runtime | More control but too much to build from scratch within the timebox. |

**LangGraph was the right call here**: nodes and edges are not just a metaphor — they are the actual execution primitives, so the visual builder and the runtime share the same model.

### Identity model — openclaw-inspired

Each agent has:
- `soul_md` — a `SOUL.md` persona document merged into the system prompt at every run (personality, communication style, values)
- `memory_md` — a `MEMORY.md` durable-memory file injected at run start (accumulated facts, user preferences, past context)
- Channel bindings — an agent (or workflow) can be permanently bound to a Telegram chat ID or a Slack channel

This gives each agent a persistent identity across runs, not just a stateless one-shot prompt.

### Stack justification

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python / FastAPI (async) | Strong AI library ecosystem, async throughout for non-blocking SSE/WebSocket |
| Runtime | LangGraph + Celery | LangGraph for graph execution, Celery for async task queue — decouples HTTP from long-running agent runs |
| Message broker | Redis | Dual-purpose: Celery broker + workflow event pub/sub for SSE streaming |
| Persistence | PostgreSQL + SQLAlchemy (async) | Relational model fits agents/workflows/steps; Alembic migrations for schema evolution |
| Frontend | Next.js 14 + React Flow + Tailwind | React Flow is purpose-built for interactive node graphs; SSR for fast initial load |
| Auth | Supabase (Google OAuth, ES256 JWT) | No password management; JWT verified via JWKS on every request |

---

## What you can configure per agent

| Dimension | Field | Notes |
|---|---|---|
| Identity | `name`, `role`, `description` | Shown on canvas nodes |
| Persona | `soul_md` | Full Markdown document merged into system prompt |
| Memory | `memory_md` | Durable facts recalled across runs |
| Brain | `model`, `provider`, `temperature`, `max_tokens` | Supports Anthropic, Gemini, OpenAI |
| Tools | `tools[]` | `web_search`, `calculator`, `get_datetime`, `list_workflows`, `run_workflow`, `pause_execution`, `resume_execution`, `terminate_execution`, `slack_list_threads`, `slack_get_thread` + MCP tools (GitHub, Notion) |
| Limits | `max_iterations`, `guardrails.max_cost_usd`, `guardrails.require_approval` | Guardrails stored as JSON for forward compatibility |
| Channels | channel bindings | Bind agent or workflow to Telegram chat ID / Slack channel |
| Schedules | `WorkflowSchedule` | One-time or repeating (every N minutes); Celery Beat fires due schedules every 60 s |

---

## Prebuilt workflow templates

### 1. Research Report
Supervisor coordinates a **Researcher** (web search) and a **Report Writer** in a feedback loop until a polished sourced report is produced. Demonstrates supervisor routing + backward edge (researcher → supervisor → writer).

### 2. Support Triage *(Telegram-ready)*
Supervisor routes a customer message to **Billing**, **Technical**, or **General** specialists. After a draft is produced, routes to a **human-approval checkpoint** before the reply is delivered. Demonstrates conditional routing + human-in-the-loop + Telegram trigger.

### 3. Slack Thread Summarizer
When @mentioned in a Slack thread, reads the full thread and replies with a concise summary in-thread. Demonstrates Slack event trigger + workflow execution.

### 4. Slack Q&A Assistant *(with mandatory approval gate)*
Single agent answers questions using web search. A **checkpoint node** always runs before the answer is posted — the draft appears in Slack with Approve/Reject Block Kit buttons. Clicking Approve resumes execution in under a second. Demonstrates deterministic flow + Block Kit interactive approval.

---

## Local setup

### Prerequisites

- Docker + Docker Compose
- Node 18+ and `pnpm`
- A **Supabase** project with Google OAuth enabled (free tier)
- An **Anthropic API key** (`sk-ant-...`)
- A **Tavily API key** (powers `web_search` — free tier at tavily.com)
- Optional: Telegram bot token (from @BotFather), Slack app tokens

### Step 1 — Backend (one command)

```bash
cd backend
cp .env.example .env   # then fill in the required keys (see below)
docker compose up --build
```

This starts **db (Postgres), redis, backend, worker, beat, ingestion**. Alembic migrations run automatically on boot. API is at `http://localhost:8000`, Swagger docs at `http://localhost:8000/docs`.

**`backend/.env` — required keys:**

```env
# LLM — at least one required
ANTHROPIC_API_KEY=sk-ant-...          # Required for default model (claude-sonnet-4-6)
GEMINI_API_KEY=                        # Optional — enables gemini-2.5-flash
OPENAI_API_KEY=                        # Optional — enables gpt-4o-mini

# Web search (required for web_search tool and Research Report template)
TAVILY_API_KEY=tvly-...

# Auth — create a project at supabase.com, enable Google OAuth
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=eyJ...              # Project API key (anon/public)
SUPABASE_JWT_SECRET=your-jwt-secret   # Found in Supabase → Settings → API → JWT Secret

# Messaging channels — optional, features degrade gracefully if not set
TELEGRAM_BOT_TOKEN=                   # From @BotFather on Telegram
TELEGRAM_WEBHOOK_SECRET=              # Any random string you choose (e.g. openssl rand -hex 16)
SLACK_BOT_TOKEN=xoxb-...              # Bot User OAuth Token from api.slack.com
SLACK_APP_TOKEN=xapp-...              # App-level token (Socket Mode) from api.slack.com

# MCP integrations — optional
GITHUB_CLIENT_ID=                     # OAuth app at github.com/settings/developers
GITHUB_CLIENT_SECRET=
NOTION_CLIENT_ID=                     # Integration at notion.so/my-integrations
NOTION_CLIENT_SECRET=
BACKEND_URL=http://localhost:8000     # Public URL if using Telegram webhooks / MCP OAuth
FRONTEND_URL=http://localhost:3000
```

**`backend/.env` — auto-configured by docker-compose (do not override):**

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/ollive_chat
REDIS_URL=redis://redis:6379/0
```

### Step 2 — Frontend

```bash
cd frontend
pnpm install
pnpm dev     # http://localhost:3000
```

**`frontend/.env.local`:**

```env
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_BACKEND_HTTP_URL=http://localhost:8000
```

### Step 3 — Try it (golden path)

1. Open `http://localhost:3000` and sign in with Google.
2. Go to **Workflows** → **Use template** → **Research Report**.
3. The builder opens with the supervisor, researcher, and writer wired together.
4. Click **Run**, type: *"3 key trends in AI agent frameworks in 2025, with sources."*
5. The live monitor shows the supervisor routing to the researcher (web_search fires), then to the writer, then ending. Token/cost per step updates in real time.

---

## Connect Telegram

1. Message [@BotFather](https://t.me/BotFather), create a bot, copy the token → `TELEGRAM_BOT_TOKEN` in `.env`.
2. Expose the backend publicly: `cloudflared tunnel --url http://localhost:8000` or `ngrok http 8000`.
3. Register the webhook:
   ```bash
   curl -X POST http://localhost:8000/api/v1/channels/telegram/set-webhook \
     -H "Authorization: Bearer <your-jwt>" \
     -H "Content-Type: application/json" \
     -d '{"webhook_url": "https://<public-url>/api/v1/webhooks/telegram"}'
   ```
4. In **Workflows → Channels**, bind your Telegram chat ID to the **Support Triage** workflow.
5. Send the bot: *"I was double-charged this month."* — the supervisor routes to the Billing specialist, the checkpoint fires, and the reply lands in the chat after approval.

---

## Connect Slack

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps).
2. **OAuth & Permissions** → bot scopes: `app_mentions:read`, `chat:write`, `channels:history`, `groups:history`.
3. **Socket Mode** → enable it → generate an **App-level token** (`xapp-...`) → `SLACK_APP_TOKEN`.
4. Install the app to your workspace → copy the **Bot User OAuth Token** (`xoxb-...`) → `SLACK_BOT_TOKEN`.
5. **Interactivity & Shortcuts** → enable Interactivity (required for Block Kit button callbacks).
6. `docker compose up` (or restart).
7. Invite the bot to a channel: `/invite @YourBot`.
8. @mention the bot: `@YourBot what are the 3 biggest AI trends in 2025?`
   - The bot replies *"Thinking…"*, runs the full agent turn (web search included), then replaces the placeholder with the complete answer.
   - Full thread history is read on every message — back-and-forth conversations work.
9. **Block Kit approval**: when a workflow with a checkpoint is triggered from the Slack Q&A Assistant template, the bot posts a Block Kit card with Approve/Reject buttons. Clicking **Approve** resumes the execution in under a second.

---

## Human-in-the-loop (checkpoint nodes)

Checkpoint nodes are supported in two modes:

| Mode | How it works |
|---|---|
| **Web UI** | The Execution Monitor shows an Approve / Reject button when a checkpoint is reached. The worker subscribes to a Redis key; clicking the button writes to that key and unblocks execution immediately. |
| **Slack Block Kit** | When a workflow is triggered from Slack, the worker posts a Block Kit interactive card to the thread. Clicking Approve or Reject in Slack resolves the same Redis key and resumes the run. |

---

## Scheduled triggers

Every workflow can have one or more schedules:

```
POST /api/v1/workflows/{id}/schedules
{
  "cron_expression": null,     # use interval_minutes instead for simple repeating
  "interval_minutes": 60,      # run every 60 minutes
  "run_once_at": null,         # or ISO timestamp for a one-time run
  "input_text": "Weekly report on AI news"
}
```

Celery Beat's `check_due_schedules` task fires every 60 seconds and enqueues any due workflows. Full CRUD at `/workflows/{id}/schedules`.

---

## MCP integrations (GitHub + Notion)

Agents can be connected to GitHub and Notion via OAuth. Once connected, tools like `github__list_repos`, `notion__search`, `notion__create_page` are selectable per agent.

- **GitHub**: create an OAuth app at github.com/settings/developers → set `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` → connect in **Settings → Integrations**.
- **Notion**: create an integration at notion.so/my-integrations → set `NOTION_CLIENT_ID` / `NOTION_CLIENT_SECRET` → connect in **Settings → Integrations**.

---

## Tests

19 integration tests in `backend/tests/` cover the three spec-required critical paths: agent CRUD, workflow execution lifecycle, and message delivery (Telegram + Slack + Block Kit). They run against an in-memory SQLite database with all external services mocked — no network, no Postgres needed.

```bash
# From the backend directory (outside Docker):
pip install redis aiosqlite
python -m pytest tests/ -q

# Or inside the running container:
docker compose exec backend pytest tests/ -q
```

**Test files:**
- `tests/test_critical_paths.py` — agent CRUD (create/read/update/delete), soul_md/memory_md persistence, workflow lifecycle (create/execute/cancel), Telegram delivery, Slack delivery, Block Kit approval delivery (11 tests)
- `tests/test_supervisor_decision.py` — supervisor routing parser: clean JSON, JSON wrapped in prose, done→\_\_end\_\_, unknown worker, garbage input (5 tests)
- `tests/test_workflow_execution.py` — workflow execution state machine, pause/resume/terminate signals (3 tests)

---

## Extending the platform

### Add a workflow template

Append an entry to `backend/app/core/workflow/templates.py`:

```python
_MY_AGENTS = {
    "supervisor": { "name": "...", "role": "supervisor", "system_prompt": "...", "tools": [], "supervisor": True },
    "worker": { "name": "...", "role": "analyst", "system_prompt": "...", "tools": ["web_search"] },
}

def _my_graph(ids: dict[str, str]) -> dict:
    return {
        "nodes": [
            _node("trigger", "trigger", 0, 120, "Input"),
            _node("supervisor", "supervisor", 260, 120, "Supervisor", "supervisor"),
            _node("worker", "agent", 560, 120, "Worker", "worker"),
            _node("end", "end", 860, 120, "End"),
        ],
        "edges": [
            _edge("trigger", "supervisor"),
            _edge("supervisor", "worker"),
            _edge("supervisor", "end"),
            _edge("worker", "supervisor"),
        ],
    }

TEMPLATES["my_template"] = {
    "key": "my_template",
    "name": "My Template",
    "description": "What it does.",
    "agents": _MY_AGENTS,
    "build_graph": _my_graph,
}
```

It appears automatically under **Workflows → templates** with no other changes.

### Add a messaging channel

1. Create `backend/app/services/<channel>_service.py` implementing:
   ```python
   async def send_message(channel_id: str, text: str, thread_ts: str | None = None) -> None: ...
   ```
2. Add a webhook endpoint in `backend/app/api/v1/endpoints/webhooks.py` that parses incoming events and calls `channel_chat.handle_channel_message(...)`.
3. Register the channel type in `backend/app/db/models/channels.py`.
4. In the worker's `execute_workflow` task, add a branch for the new channel type in `trigger_context` handling — the engine is channel-agnostic via `workflow_executions.trigger_context`.

### Add a tool

1. Create `backend/app/core/tools/<tool_name>.py` with an `async def <tool_name>(...) -> str` function.
2. Add the tool definition to `ANTHROPIC_TOOL_DEFS` in `backend/app/core/tools/registry.py`.
3. Add the implementation to `TOOL_REGISTRY` in the same file.
4. The tool is immediately selectable per agent in the UI.

---

## Project layout

```
backend/
  app/
    api/v1/endpoints/     # agents, workflows, channels, chat, webhooks, auth, sessions
    core/
      agent/              # AgentConfig, run_agent_turn loop (streaming tool calls)
      llm/                # Anthropic / Gemini / OpenAI provider adapters
      tools/              # web_search, calculator, get_datetime, workflow_tools, slack_tools, registry
      mcp/                # GitHub + Notion OAuth tool providers
      workflow/
        state.py          # WorkflowState TypedDict (LangGraph shared state)
        graph_builder.py  # React Flow JSON → LangGraph StateGraph compiler
        node_runner.py    # agent node, supervisor node, checkpoint node factories
        executor.py       # Celery task: load workflow, build graph, stream events
        events.py         # Redis pub/sub EventBus for SSE
        templates.py      # 4 prebuilt templates
    db/
      models/             # agents, workflows, channels, conversations, users
      migrations/         # Alembic versions
    services/             # agent_service, workflow_service, telegram_service, slack_service
    worker/               # Celery app + execute_workflow task + Slack socket-mode worker
  tests/
    test_critical_paths.py
    test_supervisor_decision.py
    test_workflow_execution.py

frontend/
  app/                    # Next.js 14 app router pages
  components/
    agents/               # AgentForm (Identity/Brain/Memory/Channels/Guardrails tabs), AgentCard
    workflows/            # WorkflowsPanel, WorkflowBuilder (React Flow), ExecutionMonitor, WorkflowNodes
    chat/                 # ChatInterface, ChatWindow, ChatMessage, ToolCallBubble
    monitoring/           # MonitoringPanel, TraceView
    settings/             # SettingsPanel, MCPSection
  hooks/
    useExecutionStream.ts # SSE → live state reducer (node status, edge animations, token stream)
    useWebSocket.ts       # Chat WebSocket
    useChat.ts
  lib/
    workflowGraph.ts      # graph_json ↔ React Flow node/edge conversion + edge style (solid/dotted)
    api.ts                # typed API client
    types.ts
```

---

## Roadmap (deliberately out of scope for the timebox)

- **Parallel agent swarms** — per-agent Celery tasks pulling from a shared queue for true concurrent autonomous agents (current engine: one task per execution, sequential LangGraph routing)
- **Vector memory** — pgvector semantic recall on top of `MEMORY.md` (today memory is the full file injected at run start; no write-back after a run)
- **WhatsApp channel** — Twilio adapter following the same `send_message` contract as Telegram/Slack
- **Cost guardrail enforcement** — `max_cost_usd` is persisted but not enforced mid-run; needs per-step token count piped back to the supervisor
- **Memory write-back** — post-run summarise-and-patch step to give agents true durable learning from each run
- **Workflow replay / rollback** — re-run from a specific step using persisted `workflow_steps` rows
