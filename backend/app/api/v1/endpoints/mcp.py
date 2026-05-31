"""MCP OAuth flow and connection management endpoints.

OAuth flow (front-channel redirect pattern):
  1. GET /mcp/{provider}/oauth/start  → returns { url: "https://provider.com/oauth/..." }
  2. User is redirected to the provider's consent screen in a new tab.
  3. Provider redirects to GET /mcp/{provider}/oauth/callback?code=...&state=...
  4. Backend exchanges code for token, stores MCPConnection, redirects to frontend.

env vars required:
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
    NOTION_CLIENT_ID, NOTION_CLIENT_SECRET
    FRONTEND_URL  (e.g. http://localhost:3000)
"""
import base64
import json
import logging
import secrets
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator

from app.core.config import settings
from app.db.base import get_session_factory
from app.db.models.mcp import MCPConnection
from app.dependencies.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session

# ── OAuth provider config ─────────────────────────────────────────────────────

_PROVIDERS: dict[str, dict] = {
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "scope": "repo issues:write user:read",
    },
    "notion": {
        "auth_url": "https://api.notion.com/v1/oauth/authorize",
        "token_url": "https://api.notion.com/v1/oauth/token",
        "scope": "",
    },
}


def _client_id(provider: str) -> str:
    return getattr(settings, f"{provider.upper()}_CLIENT_ID", "")


def _client_secret(provider: str) -> str:
    return getattr(settings, f"{provider.upper()}_CLIENT_SECRET", "")


def _callback_uri(provider: str) -> str:
    base = getattr(settings, "BACKEND_URL", "http://localhost:8000")
    return f"{base}/api/v1/mcp/{provider}/oauth/callback"


def _frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "http://localhost:3000")


# ── Start OAuth ───────────────────────────────────────────────────────────────

class OAuthStartResponse(BaseModel):
    url: str


@router.get("/{provider}/oauth/start", response_model=OAuthStartResponse)
async def oauth_start(
    provider: str,
    current_user: dict = Depends(get_current_user),
):
    if provider not in _PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown MCP provider: {provider}")

    client_id = _client_id(provider)
    if not client_id:
        raise HTTPException(
            status_code=501,
            detail=f"{provider.capitalize()} OAuth not configured. Set {provider.upper()}_CLIENT_ID and {provider.upper()}_CLIENT_SECRET.",
        )

    cfg = _PROVIDERS[provider]
    # Encode user_id + provider in state for CSRF protection
    state_payload = base64.urlsafe_b64encode(
        json.dumps({"user_id": current_user["id"], "provider": provider, "nonce": secrets.token_hex(8)}).encode()
    ).decode()

    params: dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": _callback_uri(provider),
        "state": state_payload,
        "response_type": "code",
    }
    if cfg["scope"]:
        params["scope"] = cfg["scope"]
    if provider == "notion":
        params["owner"] = "user"

    url = cfg["auth_url"] + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return {"url": url}


# ── OAuth Callback ────────────────────────────────────────────────────────────

@router.get("/{provider}/oauth/callback")
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    if provider not in _PROVIDERS:
        return RedirectResponse(f"{_frontend_url()}/mcp-callback?mcp_error=unknown_provider")

    # Decode state
    try:
        state_data = json.loads(base64.urlsafe_b64decode(state.encode()).decode())
        user_id = uuid.UUID(state_data["user_id"])
    except Exception:
        return RedirectResponse(f"{_frontend_url()}/mcp-callback?mcp_error=invalid_state")

    cfg = _PROVIDERS[provider]
    client_id = _client_id(provider)
    client_secret = _client_secret(provider)

    # Exchange code for token
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            if provider == "github":
                r = await client.post(
                    cfg["token_url"],
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "code": code,
                        "redirect_uri": _callback_uri(provider),
                    },
                )
                r.raise_for_status()
                token_data = r.json()
                access_token = token_data.get("access_token", "")
                scope = token_data.get("scope", "")
                if not access_token:
                    raise ValueError(f"No access_token in response: {token_data}")

                # Fetch user info
                user_r = await client.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
                )
                user_r.raise_for_status()
                gh_user = user_r.json()
                meta = {"login": gh_user.get("login"), "name": gh_user.get("name"), "avatar_url": gh_user.get("avatar_url")}

            elif provider == "notion":
                r = await client.post(
                    cfg["token_url"],
                    auth=(client_id, client_secret),
                    json={"grant_type": "authorization_code", "code": code, "redirect_uri": _callback_uri(provider)},
                    headers={"Accept": "application/json"},
                )
                r.raise_for_status()
                token_data = r.json()
                access_token = token_data.get("access_token", "")
                scope = ""
                owner = token_data.get("owner", {}).get("user", {})
                workspace = token_data.get("workspace_name", "")
                meta = {"workspace_name": workspace, "workspace_id": token_data.get("workspace_id", ""), "user_name": owner.get("name", "")}
                if not access_token:
                    raise ValueError(f"No access_token in response: {token_data}")
            else:
                raise ValueError(f"Unhandled provider: {provider}")

    except Exception as exc:
        logger.error("MCP OAuth token exchange failed for %s: %s", provider, exc)
        return RedirectResponse(f"{_frontend_url()}/mcp-callback?mcp_error=token_exchange_failed")

    # Upsert MCPConnection
    existing = await db.execute(
        select(MCPConnection).where(
            MCPConnection.user_id == user_id,
            MCPConnection.provider == provider,
        )
    )
    conn = existing.scalar_one_or_none()
    if conn:
        conn.access_token = access_token
        conn.scope = scope
        conn.meta = meta
        conn.is_active = True
    else:
        conn = MCPConnection(
            user_id=user_id,
            provider=provider,
            access_token=access_token,
            scope=scope,
            meta=meta,
        )
        db.add(conn)
    await db.commit()

    return RedirectResponse(f"{_frontend_url()}/mcp-callback?mcp_connected={provider}")


# ── List connections ──────────────────────────────────────────────────────────

class MCPConnectionResponse(BaseModel):
    provider: str
    connected: bool
    meta: dict
    scope: str | None

    class Config:
        from_attributes = True


@router.get("/connections", response_model=list[MCPConnectionResponse])
async def list_connections(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user["id"])
    result = await db.execute(
        select(MCPConnection).where(
            MCPConnection.user_id == user_id,
            MCPConnection.is_active.is_(True),
        )
    )
    conns = result.scalars().all()
    connected = {c.provider: c for c in conns}

    # Always return an entry for each known provider
    return [
        MCPConnectionResponse(
            provider=p,
            connected=p in connected,
            meta=connected[p].meta if p in connected else {},
            scope=connected[p].scope if p in connected else None,
        )
        for p in _PROVIDERS
    ]


# ── Disconnect ────────────────────────────────────────────────────────────────

@router.delete("/{provider}")
async def disconnect(
    provider: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if provider not in _PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown MCP provider: {provider}")
    user_id = uuid.UUID(current_user["id"])
    await db.execute(
        delete(MCPConnection).where(
            MCPConnection.user_id == user_id,
            MCPConnection.provider == provider,
        )
    )
    await db.commit()
    return {"disconnected": provider}
