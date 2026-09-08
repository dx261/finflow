"""Versioned API router aggregator.

Feature module routers are included here, all under the ``/api/v1``
prefix. System endpoints (health) live here as well.
"""

import asyncio
import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.core.redis import ping_redis
from app.modules.accounts.router import router as accounts_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.banks.router import router as banks_router

logger = logging.getLogger("finflow")

api_router = APIRouter(prefix=settings.api_v1_prefix)
api_router.include_router(auth_router)
api_router.include_router(banks_router)
api_router.include_router(accounts_router)
api_router.include_router(audit_router)


async def check_database() -> str:
    """Probe the database with a round-trip query.

    Returns ``"ok"`` when reachable, otherwise ``"unavailable"``. The probe
    is bounded by a short timeout so a downed database never hangs or
    crashes the endpoint.
    """
    try:
        async with asyncio.timeout(3):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        logger.warning("database_health_check_failed", exc_info=True)
        return "unavailable"


@api_router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Liveness probe.

    Reports service status plus the state of each infrastructure
    dependency. Dependencies degrade gracefully — an unavailable database
    never prevents the API from booting or responding.
    """
    return {
        "status": "ok",
        "database": await check_database(),
        "redis": await ping_redis(),
    }
