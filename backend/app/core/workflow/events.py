"""Live workflow events: published to Redis pub/sub for SSE streaming and
optionally persisted to execution_events (only external/durable I/O events)."""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


def channel_for(execution_id: str) -> str:
    return f"workflow:{execution_id}"


class EventBus:
    """Thin wrapper over a Redis connection for publishing execution events.
    One bus per execution run; reused across all nodes in that run."""

    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        self._redis: Optional[aioredis.Redis] = None

    async def _conn(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL)
        return self._redis

    async def publish(self, event_type: str, **fields: Any) -> None:
        payload = {
            "type": event_type,
            "execution_id": self.execution_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            **fields,
        }
        try:
            redis = await self._conn()
            await redis.publish(channel_for(self.execution_id), json.dumps(payload))
        except Exception as e:  # never let telemetry kill the run
            logger.warning("Event publish failed (%s): %s", event_type, e)

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None
