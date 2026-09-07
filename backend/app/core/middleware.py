"""HTTP middleware: request trace-ID propagation."""

import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Ensure every request carries a trace ID.

    Accepts an inbound ``X-Request-ID`` header (for cross-service
    propagation) or generates a fresh UUID, exposes it through
    ``trace_id_var`` and ``request.state.trace_id`` and echoes it back
    on the response.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        trace_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.trace_id = trace_id
        token = trace_id_var.set(trace_id)
        try:
            response = await call_next(request)
        finally:
            trace_id_var.reset(token)
        response.headers["X-Request-ID"] = trace_id
        return response
