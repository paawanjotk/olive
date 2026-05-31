"""MCP tool registry — resolves provider tokens and dispatches tool calls.

Tool names use double-underscore provider prefixes:
    github__list_repos, github__get_file, …
    notion__search, notion__create_page, …
"""
import logging
import uuid
from typing import Any

from sqlalchemy import select

from app.core.mcp.github_tools import GITHUB_TOOL_DEFS, GITHUB_TOOL_FNS
from app.core.mcp.notion_tools import NOTION_TOOL_DEFS, NOTION_TOOL_FNS

logger = logging.getLogger(__name__)

_PROVIDER_DEFS: dict[str, list[dict]] = {
    "github": GITHUB_TOOL_DEFS,
    "notion": NOTION_TOOL_DEFS,
}

_PROVIDER_FNS: dict[str, dict] = {
    "github": GITHUB_TOOL_FNS,
    "notion": NOTION_TOOL_FNS,
}


async def _get_token(provider: str, user_id: str) -> str | None:
    """Fetch the stored OAuth token for (provider, user). Returns None if not connected."""
    from app.db.base import get_session_factory
    from app.db.models.mcp import MCPConnection
    async with get_session_factory()() as db:
        result = await db.execute(
            select(MCPConnection).where(
                MCPConnection.user_id == uuid.UUID(user_id),
                MCPConnection.provider == provider,
                MCPConnection.is_active.is_(True),
            )
        )
        conn = result.scalar_one_or_none()
        return conn.access_token if conn else None


def get_mcp_tool_defs_sync(providers: list[str]) -> list[dict]:
    """Return Anthropic tool def dicts for the given providers (no DB needed)."""
    defs = []
    for provider in providers:
        defs.extend(_PROVIDER_DEFS.get(provider, []))
    return defs


async def get_mcp_tool_defs(providers: list[str], user_id: str) -> list[dict]:
    """Return tool defs only for providers that have a valid stored token."""
    defs = []
    for provider in providers:
        token = await _get_token(provider, user_id)
        if token:
            defs.extend(_PROVIDER_DEFS.get(provider, []))
        else:
            logger.debug("MCP provider %s has no token for user %s — skipping", provider, user_id)
    return defs


async def execute_mcp_tool(tool_name: str, tool_input: dict, user_id: str | None) -> str:
    """Execute an MCP tool by name.

    tool_name format: '{provider}__{function}', e.g. 'github__list_repos'.
    The provider's stored OAuth token is fetched and injected automatically.
    """
    if "__" not in tool_name:
        raise ValueError(f"Not an MCP tool name: {tool_name}")

    provider, _ = tool_name.split("__", 1)
    provider_fns = _PROVIDER_FNS.get(provider)
    if provider_fns is None:
        raise ValueError(f"Unknown MCP provider: {provider}")

    fn = provider_fns.get(tool_name)
    if fn is None:
        raise ValueError(f"Unknown MCP tool: {tool_name}")

    if not user_id:
        return f"Error: no user context for MCP tool {tool_name}"

    token = await _get_token(provider, user_id)
    if not token:
        return (
            f"Error: {provider} is not connected for this user. "
            f"Go to Settings → Integrations → {provider.capitalize()} to connect."
        )

    try:
        return await fn(token=token, **tool_input)
    except Exception as exc:
        logger.warning("MCP tool %s failed: %s", tool_name, exc)
        return f"Error calling {tool_name}: {exc}"


__all__ = ["get_mcp_tool_defs", "get_mcp_tool_defs_sync", "execute_mcp_tool"]
