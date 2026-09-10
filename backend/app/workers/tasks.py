"""Celery tasks.

The heavy lifting lives in the async services; these thin tasks adapt them
for the synchronous Celery worker runtime. Tasks are bound to the
project's configured ``celery_app`` (Redis broker) — never the unconfigured
default app.
"""

import asyncio
import uuid

from app.core.database import AsyncSessionLocal
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
