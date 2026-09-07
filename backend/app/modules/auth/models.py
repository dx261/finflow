"""User model and enums."""

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(StrEnum):
    """Access level for a user."""

    OWNER = "OWNER"
    VIEWER = "VIEWER"


class UserStatus(StrEnum):
    """Lifecycle state of a user account."""

    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole), default=UserRole.VIEWER, nullable=False
    )
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False
    )
