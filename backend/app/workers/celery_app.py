"""Celery application factory.

Redis is the broker and result backend. Tasks are auto-discovered from
``app.workers.tasks``. Run the worker with::

    celery -A app.workers.celery_app worker
"""

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
