"""Authentication request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.auth.models import UserRole, UserStatus

_PASSWORD_MIN = 8
_PASSWORD_MAX = 72  # bcrypt hard limit


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=_PASSWORD_MIN, max_length=_PASSWORD_MAX)
    registration_token: str | None = Field(default=None, max_length=256)


class LoginRequest(BaseModel):
    login: str = Field(description="Username or email")
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    role: UserRole
    status: UserStatus
    created_at: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
