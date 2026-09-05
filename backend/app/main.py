"""FinFlow FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging

logger = logging.getLogger("finflow")

configure_logging()


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
    def health() -> dict[str, str]:
        """Liveness probe.

        Reports service status plus the state of each infrastructure
        dependency. Database and Redis clients are wired in later tasks, so
        for now they report ``not_configured``.
        """
        return {
            "status": "ok",
            "database": "not_configured",
            "redis": "not_configured",
        }

    return app


app = create_app()
