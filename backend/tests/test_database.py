"""Database infrastructure integration tests.

These run against a temporary file-based SQLite database, so no database
server is required. They exercise the async engine, session factory, UUID
primary keys, timestamps and transaction helpers end to end.
"""

import uuid

import pytest
from app.core.database import (
    AsyncSessionLocal,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    commit_or_rollback,
    engine,
    session_scope,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column


class DummyRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dummy_records"

    name: Mapped[str] = mapped_column(nullable=False)


@pytest.fixture
async def prepared_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_create_and_read_record(prepared_db: None) -> None:
    async with AsyncSessionLocal() as session:
        record = DummyRecord(name="hello")
        session.add(record)
        await session.commit()
        record_id = record.id

    async with AsyncSessionLocal() as session:
        result = await session.get(DummyRecord, record_id)
        assert result is not None
        assert result.name == "hello"


async def test_uuid_primary_key_and_timestamps(prepared_db: None) -> None:
    async with AsyncSessionLocal() as session:
        record = DummyRecord(name="timestamps")
        session.add(record)
        await session.commit()

        assert isinstance(record.id, uuid.UUID)
        assert record.created_at is not None
        assert record.updated_at is not None

        # Updating a row must succeed and keep the object consistent.
        record.name = "timestamps-updated"
        await session.commit()
        assert record.name == "timestamps-updated"


async def test_unique_ids_per_row(prepared_db: None) -> None:
    async with AsyncSessionLocal() as session:
        first = DummyRecord(name="a")
        second = DummyRecord(name="b")
        session.add_all([first, second])
        await session.commit()
        assert first.id != second.id


async def test_commit_or_rollback_rolls_back_on_integrity_error(
    prepared_db: None,
) -> None:
    async with AsyncSessionLocal() as session:
        # name is NOT NULL; flushing without it must raise and then roll back.
        session.add(DummyRecord())  # type: ignore[call-arg]
        with pytest.raises(IntegrityError):
            await commit_or_rollback(session)

        # After the rollback nothing should be persisted.
        count = await session.scalar(select(func.count()).select_from(DummyRecord))
        assert count == 0


async def test_session_scope_rolls_back_on_error(prepared_db: None) -> None:
    with pytest.raises(ValueError, match="boom"):
        async with session_scope() as session:
            session.add(DummyRecord(name="doomed"))
            raise ValueError("boom")

    async with AsyncSessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(DummyRecord))
        assert count == 0


async def test_session_scope_commits_on_success(prepared_db: None) -> None:
    async with session_scope() as session:
        session.add(DummyRecord(name="persisted"))

    async with AsyncSessionLocal() as session:
        result = await session.scalar(select(DummyRecord))
        assert result is not None
        assert result.name == "persisted"
