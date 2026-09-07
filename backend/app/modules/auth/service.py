"""Authentication business logic."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    InvalidCredentialsError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.auth.models import User, UserRole, UserStatus
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import TokenPair, UserCreate


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = UserRepository(session)

    async def register(self, payload: UserCreate) -> User:
        if await self.repository.get_by_username(payload.username) is not None:
            raise ConflictError("Username already exists.")
        if await self.repository.get_by_email(payload.email) is not None:
            raise ConflictError("Email already registered.")

        # The very first user of the system becomes the OWNER; everyone
        # else is a read-only VIEWER.
        role = UserRole.OWNER if await self.repository.count() == 0 else UserRole.VIEWER
        user = await self.repository.create(
            username=payload.username,
            email=str(payload.email),
            password_hash=hash_password(payload.password),
            role=role,
        )
        await self.session.commit()
        return user

    async def authenticate(self, login: str, password: str) -> User:
        user = await self.repository.get_by_login(login)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid username or password.")
        if user.status != UserStatus.ACTIVE:
            raise AuthenticationError("User is disabled.", code="USER_DISABLED")
        return user

    def issue_tokens(self, user: User) -> TokenPair:
        return TokenPair(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def refresh(self, refresh_token: str) -> TokenPair:
        payload = decode_token(refresh_token, expected_type="refresh")
        user_id = uuid.UUID(payload["sub"])
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError("User no longer exists.")
        if user.status != UserStatus.ACTIVE:
            raise AuthenticationError("User is disabled.", code="USER_DISABLED")
        return self.issue_tokens(user)
