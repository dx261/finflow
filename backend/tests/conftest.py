"""Shared test configuration.

Overrides the application database URL with a temporary file-based SQLite
database before any application module is imported, so the whole test suite
runs without a database server. Production remains PostgreSQL (asyncpg).
"""

import os
import tempfile

_test_dir = tempfile.mkdtemp(prefix="finflow_test_")
_db_url = f"sqlite+aiosqlite:///{_test_dir.replace(os.sep, '/')}/test.db"
# Plain DATABASE_URL (no prefix) matches the pydantic-settings field name.
os.environ["DATABASE_URL"] = _db_url
