"""Authentication API endpoints.

Routers only orchestrate; all logic lives in :class:`AuthService`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import LoginRequest, RefreshRequest, TokenPair, UserCreate, UserRead
from app.modules.auth.service import AuthService

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(payload: UserCreate, session: DbSession) -> User:
    return await AuthService(session).register(payload)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, session: DbSession) -> TokenPair:
    service = AuthService(session)
    user = await service.authenticate(payload.login, payload.password)
    return service.issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, session: DbSession) -> TokenPair:
    return await AuthService(session).refresh(payload.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser) -> User:
    return current_user
