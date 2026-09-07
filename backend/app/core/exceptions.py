"""Application exception hierarchy and unified error envelope.

Every client-visible error is returned as::

    {"code": "...", "message": "...", "trace_id": "..."}

so the frontend never receives a raw Python traceback.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.middleware import trace_id_var

logger = logging.getLogger("finflow")

# Stable machine-readable codes for common HTTP statuses.
_CODE_FOR_STATUS: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
}


class FinFlowError(Exception):
    """Base class for application errors.

    Carries a stable ``code`` and an HTTP ``status_code``. Subclasses set
    sensible defaults; instances can override both.
    """

    status_code: int = 400
    code: str = "ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(FinFlowError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(FinFlowError):
    status_code = 409
    code = "CONFLICT"


class InsufficientPlanningFundsError(FinFlowError):
    status_code = 409
    code = "INSUFFICIENT_PLANNING_FUNDS"


class InvalidStateTransitionError(FinFlowError):
    status_code = 409
    code = "INVALID_STATE_TRANSITION"


class DuplicateImportError(ConflictError):
    code = "DUPLICATE_IMPORT"


class AuthenticationError(FinFlowError):
    status_code = 401
    code = "UNAUTHORIZED"


class InvalidCredentialsError(AuthenticationError):
    code = "INVALID_CREDENTIALS"


def _trace_id_for(request: Request) -> str:
    """Resolve the current request trace ID.

    The generic 500 handler runs in the outer error middleware, after the
    trace middleware has already reset its contextvar, so we fall back to
    the value stashed on ``request.state``.
    """
    return getattr(request.state, "trace_id", None) or trace_id_var.get() or ""


def error_payload(code: str, message: str, trace_id: str | None = None) -> dict[str, Any]:
    """Build the unified error envelope."""
    return {
        "code": code,
        "message": message,
        "trace_id": trace_id,
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Install the unified error handlers on the application."""

    @app.exception_handler(FinFlowError)
    async def finflow_error_handler(request: Request, exc: FinFlowError) -> JSONResponse:
        logger.warning("finflow_error", extra={"code": exc.code, "error_message": exc.message})
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, _trace_id_for(request)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = exc.errors()
        if details:
            loc = ".".join(str(part) for part in details[0]["loc"])
            message = f"{loc}: {details[0]['msg']}"
        else:
            message = "Request validation failed."
        return JSONResponse(
            status_code=422,
            content=error_payload("VALIDATION_ERROR", message, _trace_id_for(request)),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _CODE_FOR_STATUS.get(exc.status_code, "ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code, str(exc.detail), _trace_id_for(request)),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content=error_payload(
                "INTERNAL_ERROR",
                "An unexpected error occurred.",
                _trace_id_for(request),
            ),
        )
