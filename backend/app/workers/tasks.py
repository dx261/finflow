"""Celery tasks.

The heavy lifting lives in the async services; these thin tasks adapt them
for the synchronous Celery worker runtime. Tasks are bound to the
project's configured ``celery_app`` (Redis broker) — never the unconfigured
default app.
"""

import asyncio
import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.modules.auth.models import User
from app.modules.recurring.service import RecurringService
from app.modules.statements.service import StatementService
from app.workers.celery_app import celery_app


async def _run_process_import(import_id: str) -> dict:
    """Async core of the statement import task."""
    async with AsyncSessionLocal() as session:
        record = await StatementService(session).process_import(uuid.UUID(import_id))
        return {
            "import_id": str(record.id),
            "status": record.status.value,
            "success_rows": record.success_rows,
            "failed_rows": record.failed_rows,
        }


@celery_app.task(name="statements.process_import")
def process_import_task(import_id: str) -> dict:
    """Parse and insert a staged statement file."""
    return asyncio.run(_run_process_import(import_id))


async def _run_generate_recurring(days_ahead: int) -> dict:
    """Materialize due recurring payments for every user (idempotent)."""
    today = date.today()
    horizon = today + timedelta(days=days_ahead)
    total = 0
    async with AsyncSessionLocal() as session:
        user_ids = list(await session.scalars(select(User.id)))
        for user_id in user_ids:
            total += await RecurringService(session).generate_due_plans(user_id, today, horizon)
    return {"generated": total, "window_days": days_ahead}


@celery_app.task(name="recurring.generate_plans")
def generate_recurring_plans_task(days_ahead: int = 30) -> dict:
    """Daily beat job: generate upcoming recurring payment plans."""
    return asyncio.run(_run_generate_recurring(days_ahead))
