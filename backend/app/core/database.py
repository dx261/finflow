"""Database infrastructure.

Provides the async engine, session factory, declarative base and common
model mixins (UUID primary key, created/updated timestamps) plus small
transaction helpers. Production runs on PostgreSQL via asyncpg; tests
override ``DATABASE_URL`` with SQLite (aiosqlite).
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.core.config import settings

_poolclass = NullPool if settings.database_poolclass == "null" else None

engine = create_async_engine(settings.database_url, pool_pre_ping=True, poolclass=_poolclass)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def _utcnow() -> datetime:
    """Timezone-aware UTC now, computed client-side.

    Python-side timestamp defaults keep the value known to the ORM
    immediately after flush, so reading it never triggers a lazy reload —
    which is illegal in an async context and would raise MissingGreenlet.
    """
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for every ORM model in the application."""


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key generated in Python."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        yield session


async def commit_or_rollback(session: AsyncSession) -> None:
    """Commit the session, rolling back and re-raising on failure."""
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transactional scope: commits on success, rolls back on failure.

    Money-critical operations (allocation confirm, reservation, settlement,
    reconciliation confirm) must run inside this scope so a failure in any
    step rolls the whole operation back.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
