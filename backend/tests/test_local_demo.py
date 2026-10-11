"""SQLite showcase behavior without a Redis server or a worker."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

from app.core.config import settings
from app.core.redis import redis_client


async def test_readiness_skips_redis_in_local_demo(client, monkeypatch):
    monkeypatch.setattr(settings, "local_demo", True)
    ping = AsyncMock(side_effect=AssertionError("Redis must not be contacted"))
    monkeypatch.setattr(redis_client, "ping", ping)
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "disabled"}
    ping.assert_not_called()


async def test_local_statement_upload_is_processed_without_worker(
    client, seeded_banks, monkeypatch
):
    monkeypatch.setattr(settings, "local_demo", True)
    monkeypatch.setattr(settings, "demo_mode", True)
    banks = (await client.get("/api/v1/banks")).json()
    bank_id = next(bank["id"] for bank in banks if bank["code"] == "GENERIC")
    account = await client.post(
        "/api/v1/accounts", json={"bank_id": bank_id, "name": "SQLite demo"}
    )
    assert account.status_code == 201
    content = "交易日期,摘要,收入金额,支出金额,余额\n2026-10-01,模拟工资,1000.00,,1000.00\n"
    uploaded = await client.post(
        "/api/v1/statements/upload",
        data={"account_id": account.json()["id"]},
        files={"file": ("demo.csv", content.encode("utf-8-sig"), "text/csv")},
    )
    assert uploaded.status_code == 202
    assert uploaded.json()["status"] == "SUCCESS"
    assert len((await client.get("/api/v1/transactions")).json()) == 1


def test_initializer_is_persistent_and_idempotent(tmp_path):
    project = Path(__file__).resolve().parents[2]
    db_path = tmp_path / "showcase.sqlite3"
    env = {
        **os.environ,
        "APP_ENV": "development",
        "LOCAL_DEMO": "true",
        "DEMO_MODE": "true",
        "DATABASE_URL": f"sqlite+aiosqlite:///{db_path.as_posix()}",
        "DATA_DIR": str(tmp_path / "uploads"),
        "REDIS_URL": "redis://127.0.0.1:1/0",
        "PYTHONIOENCODING": "utf-8",
    }
    command = [sys.executable, str(project / "scripts/init_demo.py")]
    first = subprocess.run(
        command, cwd=project, env=env, capture_output=True, encoding="utf-8", timeout=30
    )
    assert first.returncode == 0, first.stderr
    with sqlite3.connect(db_path) as connection:
        counts = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("accounts", "payment_plans", "transactions", "cash_flow_plans")
        )
        assert counts == (5, 6, 2, 3)
        connection.execute("UPDATE accounts SET name='Preserved edit' WHERE currency='USD'")
    second = subprocess.run(
        command, cwd=tmp_path, env=env, capture_output=True, encoding="utf-8", timeout=30
    )
    assert second.returncode == 0, second.stderr
    with sqlite3.connect(db_path) as connection:
        assert (
            tuple(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("accounts", "payment_plans", "transactions", "cash_flow_plans")
            )
            == counts
        )
        assert (
            connection.execute("SELECT name FROM accounts WHERE currency='USD'").fetchone()[0]
            == "Preserved edit"
        )
