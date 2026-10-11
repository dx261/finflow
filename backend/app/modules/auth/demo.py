"""Opt-in anonymous demo principal; never reuse a real workspace owner."""

import secrets
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError
from app.core.security import hash_password
from app.modules.auth.models import User, UserRole, UserStatus

DEMO_USER_ID = uuid.UUID("693529ea-d977-43f0-9d46-1a6b8ce43eab")


async def get_demo_user(session: AsyncSession) -> User:
    """Create once, serialize first requests, and preserve demo data thereafter."""
    user = await session.get(User, DEMO_USER_ID)
    if user is None and session.get_bind().dialect.name == "postgresql":
        await session.execute(text("SELECT pg_advisory_xact_lock(1179460688)"))
        user = await session.get(User, DEMO_USER_ID)
    if user is None:
        user = User(
            id=DEMO_USER_ID,
            username="finflow_demo",
            email="finflow_demo@example.com",
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role=UserRole.OWNER,
            status=UserStatus.ACTIVE,
        )
        session.add(user)
        await session.commit()
    if user.status != UserStatus.ACTIVE or user.role != UserRole.OWNER:
        raise PermissionDeniedError("Demo user is disabled or misconfigured.")
    return user
