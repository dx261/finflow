"""User data access."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User, UserRole


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_login(self, login: str) -> User | None:
        """Find a user by username or email."""
        result = await self.session.scalar(
            select(User).where(or_(User.username == login, User.email == login))
        )
        return result

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.scalar(select(User).where(User.username == username))
        return result

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.scalar(select(User).where(User.email == email))
        return result

    async def count(self) -> int:
        result = await self.session.scalar(select(func.count()).select_from(User))
        return int(result or 0)

    async def create(
        self,
        username: str,
        email: str,
        password_hash: str,
        role: UserRole,
    ) -> User:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
        )
        self.session.add(user)
        await self.session.flush()
        return user
