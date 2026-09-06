"""FinFlow FastAPI application entrypoint."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.core.logging import configure_logging

logger = logging.getLogger("finflow")

configure_logging()


async def check_database() -> str:
    """Probe the database with a round-trip query.

    Returns ``"ok"`` when reachable, otherwise ``"unavailable"``. The probe
    is bounded by a short timeout so a downed database never hangs or
    crashes the health endpoint.
    """
    try:
        async with asyncio.timeout(3):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        logger.warning("database_health_check_failed", exc_info=True)
        return "unavailable"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle hooks."""
    logger.info(
        "finflow_started",
        extra={"app": settings.app_name, "env": settings.app_env},
    )
    yield
    logger.info("finflow_shutdown")


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get(f"{settings.api_v1_prefix}/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Liveness probe.

        Reports service status plus the state of each infrastructure
        dependency. Dependencies degrade gracefully — an unavailable
        database never prevents the API from booting or responding.
        """
        return {
            "status": "ok",
            "database": await check_database(),
            "redis": "not_configured",
        }

    return app


app = create_app()
