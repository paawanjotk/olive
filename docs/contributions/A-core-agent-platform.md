# Core Agent & Chat Platform

**Owner:** Satish Rathod &lt;satish.rathod.ov@gmail.com&gt;

The foundational layer the rest of the product is built on: the agent runtime,
the LLM abstraction, the tool system, real-time chat, and authentication.

## Scope

- **Agent loop** — single-agent execution core (`backend/app/core/agent/`).
- **Multi-provider LLM abstraction** — one interface over Anthropic, Gemini,
  and OpenAI providers with a pluggable manager (`backend/app/core/llm/`).
- **Tool system** — registry plus built-in tools (calculator, datetime,
  web search) in `backend/app/core/tools/`.
- **Real-time chat** — WebSocket streaming, chat UI, and session handling
  (`frontend/components/chat/`, `frontend/hooks/useWebSocket.ts`).
- **Authentication** — Supabase auth with JWT verification and auth-guarded
  API dependencies (`backend/app/dependencies/auth.py`, `frontend/contexts/AuthContext.tsx`).
- **Thread context** — per-thread context separation and a cross-thread
  context tool.

## Highlights

- Established the base chat system and single-agent usage pattern.
- Added Supabase auth with JWT verification across backend and frontend.
- Introduced thread context separation with cross-thread access via a tool.
