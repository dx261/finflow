"""Authentication dependencies for protected endpoints."""

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, InvalidCredentialsError
from app.core.security import decode_token
from app.modules.auth.models import User, UserStatus
from app.modules.auth.repository import UserRepository

_bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]


async def get_current_user(
    session: DbSession,
    credentials: BearerCredentials = None,
) -> User:
    """Validate the bearer token and load the authenticated user.

    Used as a FastAPI dependency on protected endpoints.
    """
    if credentials is None:
        raise AuthenticationError("Not authenticated.", code="NOT_AUTHENTICATED")

    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = uuid.UUID(payload["sub"])

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise InvalidCredentialsError("User no longer exists.")
    if user.status != UserStatus.ACTIVE:
        raise AuthenticationError("User is disabled.", code="USER_DISABLED")
    return user
