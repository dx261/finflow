"""Authentication dependencies for protected endpoints."""

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    PermissionDeniedError,
)
from app.core.security import decode_token
from app.modules.auth.demo import DEMO_USER_ID, get_demo_user
from app.modules.auth.models import User, UserRole, UserStatus
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
    if settings.demo_mode:
        return await get_demo_user(session)
    if credentials is None:
        raise AuthenticationError("Not authenticated.", code="NOT_AUTHENTICATED")

    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = uuid.UUID(payload["sub"])
    if user_id == DEMO_USER_ID:
        raise AuthenticationError("Demo mode is disabled.", code="DEMO_DISABLED")

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise InvalidCredentialsError("User no longer exists.")
    if user.status != UserStatus.ACTIVE:
        raise AuthenticationError("User is disabled.", code="USER_DISABLED")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_data_owner_id(current_user: CurrentUser, session: DbSession) -> uuid.UUID:
    """Resolve the single workspace data owner for OWNER/VIEWER reads.

    FinFlow is currently a single-workspace application.  OWNER mutates the
    data and VIEWER reads the same dataset; records therefore remain keyed to
    the owner until a first-class workspace table is introduced.
    """
    if current_user.role == UserRole.OWNER:
        return current_user.id
    owner = await UserRepository(session).get_active_owner()
    if owner is None:
        raise PermissionDeniedError("No active workspace owner is available.")
    return owner.id


DataOwnerId = Annotated[uuid.UUID, Depends(get_data_owner_id)]


def require_owner(current_user: CurrentUser) -> User:
    """Dependency that permits only OWNER users."""
    if current_user.role != UserRole.OWNER:
        raise PermissionDeniedError("Owner role required.")
    return current_user


OwnerUser = Annotated[User, Depends(require_owner)]
