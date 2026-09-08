"""Bank catalog model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Bank(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A statement data source (ICBC, CMB, ...), not a bank connection."""

    __tablename__ = "banks"

    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="CN", nullable=False)
    logo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    statement_parser_type: Mapped[str] = mapped_column(
        String(30), default="GENERIC", nullable=False
    )
