from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth, health, users, sessions, chat, agents, workflows, channels, webhooks, mcp,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(channels.router, prefix="/channels", tags=["channels"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(chat.router, prefix="/ws", tags=["websocket"])
api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
