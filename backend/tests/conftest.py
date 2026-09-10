"""Shared test configuration.

Overrides the application database URL with a temporary file-based SQLite
database before any application module is imported, so the whole test suite
runs without a database server. Production remains PostgreSQL (asyncpg).

Tests use an async httpx client with ASGI transport so the application and
the database fixtures share a single event loop (no cross-loop connection
issues).
"""

import os
import tempfile
from collections.abc import AsyncIterator

_test_dir = tempfile.mkdtemp(prefix="finflow_test_")
_db_url = f"sqlite+aiosqlite:///{_test_dir.replace(os.sep, '/')}/test.db"
# Plain env names (no prefix) match the pydantic-settings field names.
os.environ["DATABASE_URL"] = _db_url
# NullPool avoids reusing connections across event loops.
os.environ["DATABASE_POOLCLASS"] = "null"
# Point Redis at a closed port so the suite never depends on a server.
os.environ["REDIS_URL"] = "redis://127.0.0.1:1/0"
# Uploaded statement files land in a temp directory during tests.
os.environ["DATA_DIR"] = os.path.join(_test_dir, "data")
# Tests use the synchronous import path; never dispatch to Celery.
os.environ["STATEMENT_IMPORT_ASYNC"] = "false"

import httpx  # noqa: E402
import pytest  # noqa: E402
from app.core.database import AsyncSessionLocal, Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.banks.seed import seed_default_banks  # noqa: E402
from app.modules.categories.seed import seed_default_categories  # noqa: E402


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Async client running the app in the same event loop as the tests."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def db_reset() -> None:
    """Drop and recreate every table (all models registered)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def seeded_banks(db_reset) -> None:
    """Reset the schema and insert the default bank catalog."""
    async with AsyncSessionLocal() as session:
        await seed_default_banks(session)
    yield


@pytest.fixture
async def seeded_categories(db_reset) -> None:
    """Reset the schema and insert the default categories."""
    async with AsyncSessionLocal() as session:
        await seed_default_categories(session)
    yield


@pytest.fixture
async def auth_headers(client, db_reset) -> dict[str, str]:
    """Register an OWNER user and return authenticated headers."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": "owner", "email": "owner@test.dev", "password": "password123"},
    )
    assert response.status_code == 201
    login = await client.post(
        "/api/v1/auth/login", json={"login": "owner", "password": "password123"}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}
