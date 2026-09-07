"""Password hashing and JWT utilities.

Passwords are hashed with bcrypt; never stored in plaintext. Access and
refresh tokens are signed JWTs carrying the user id and a token type so a
refresh token can never be used as an access token.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationError

_ACCESS = "access"
_REFRESH = "refresh"


def hash_password(password: str) -> str:
    """Hash a password with a fresh bcrypt salt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID) -> str:
    """Issue a short-lived access token."""
    return _create_token(
        str(user_id), _ACCESS, timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    """Issue a long-lived refresh token."""
    return _create_token(
        str(user_id), _REFRESH, timedelta(days=settings.jwt_refresh_token_expire_days)
    )


def decode_token(token: str, expected_type: str = _ACCESS) -> dict[str, Any]:
    """Validate a token and return its payload.

    Raises :class:`AuthenticationError` for any invalid, expired or
    wrong-typed token.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired token.", code="INVALID_TOKEN") from exc
    if payload.get("type") != expected_type:
        raise AuthenticationError("Invalid token type.", code="INVALID_TOKEN")
    return payload
