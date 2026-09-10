"""FinFlow FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import TraceIDMiddleware
from app.models import Base  # noqa: F401  (register all models on metadata)
from app.modules.banks.seed import seed_default_banks
from app.modules.categories.seed import seed_default_categories

logger = logging.getLogger("finflow")

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle hooks."""
    logger.info(
        "finflow_started",
        extra={"app": settings.app_name, "env": settings.app_env},
    )
    # Seed default catalogs. Best-effort: a missing database must never
    # prevent the API from booting.
    try:
        async with AsyncSessionLocal() as session:
            banks = await seed_default_banks(session)
            categories = await seed_default_categories(session)
            if banks or categories:
                logger.info(
                    "catalogs_seeded",
                    extra={"banks_created": banks, "categories_created": categories},
                )
    except Exception:
        logger.warning("catalog_seed_failed", exc_info=True)
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

    # Middleware order matters: the last-added middleware is the outermost.
    # Trace-ID first, then CORS so CORS wraps every response.
    app.add_middleware(TraceIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)

    return app


app = create_app()
