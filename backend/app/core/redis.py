"""Redis client infrastructure.

Redis backs the Celery broker/result store, dashboard caching, distributed
locks and idempotency keys. The client is created lazily and shared via a
module-level singleton.
"""

import asyncio
import logging
from typing import Any

from redis.asyncio import Redis, from_url

from app.core.config import settings

logger = logging.getLogger("finflow")

redis_client: Redis = from_url(settings.redis_url, decode_responses=True)


async def ping_redis() -> str:
    """Probe Redis with a bounded-time PING.

    Returns ``"ok"`` when reachable, otherwise ``"unavailable"``. A downed
    Redis must never crash the API, so this degrades gracefully.
    """
    try:
        async with asyncio.timeout(3):
            await redis_client.ping()
        return "ok"
    except Exception:
        logger.warning("redis_health_check_failed", exc_info=True)
        return "unavailable"


async def get_redis() -> Any:
    """FastAPI dependency returning the shared Redis client."""
    return redis_client
