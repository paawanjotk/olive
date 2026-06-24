# Channels & Integrations

**Owner:** Paawanjot Kaur &lt;paawanjotkaur05@gmail.com&gt;

Connects the platform to the outside world: messaging channels and external
tool integrations via MCP.

## Scope

- **Direct chat channels** — Slack and Telegram channels with a unified
  connect API (`backend/app/services/slack_service.py`,
  `telegram_service.py`, `channel_connector.py`, `endpoints/channels.py`,
  `endpoints/webhooks.py`).
- **Live status in Slack** — real-time tool-call status updates pushed to
  Slack during a run (`backend/app/worker/slack_worker.py`).
- **MCP support** — Model Context Protocol integration with GitHub and Notion
  tools, OAuth callback, and a connection registry
  (`backend/app/core/mcp/`, `frontend/components/settings/MCPSection.tsx`).
- **Channel onboarding** — join-channel option in settings.

## Highlights

- Built the unified connect API for Slack/Telegram direct chat channels.
- Streamed live tool-call status updates into Slack.
- Added MCP support with GitHub/Notion tools and OAuth.
