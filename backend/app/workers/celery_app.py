"""Celery application factory.

Redis is the broker and result backend. Tasks are auto-discovered from
``app.workers.tasks``. Run the worker with::

    DATABASE_POOLCLASS=null celery -A app.workers.celery_app worker

``DATABASE_POOLCLASS=null`` matters: tasks run under ``asyncio.run()``,
which creates a fresh event loop per task. The default SQLAlchemy pool
reuses connections across loops and fails with "Event loop is closed";
NullPool gives each task its own connection (the tests use it too).
On Windows, add ``--pool=solo`` to avoid billiard's prefork shared-memory
issues when the worker is launched from a detached script.
"""

from datetime import timedelta

from celery import Celery

import app.models  # noqa: F401  (register all models on Base.metadata)
from app.core.config import settings

celery_app = Celery(
    "finflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "generate-recurring-plans-daily": {
        "task": "recurring.generate_plans",
        "schedule": timedelta(days=1),
        "args": (30,),
    }
}
