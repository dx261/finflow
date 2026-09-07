"""Structured JSON logging configuration.

Every log record is emitted as a single JSON line on stdout so that
container log aggregators can parse it without custom multiline handling.
"""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import settings
from app.core.middleware import trace_id_var


class TraceIDFilter(logging.Filter):
    """Attach the current request trace ID to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """Format log records as one-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": record.__dict__.get("trace_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Install the JSON formatter and trace filter on the root logger."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(TraceIDFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if settings.debug else logging.INFO)
