"""Account model.

Three distinct balance concepts (see CODING_PLAN.md §13):

- ``actual_balance``     real balance from the latest statement/manual entry
- ``reserved_amount``    virtual funds reserved for future payments (derived)
- ``planning_available`` actual - reserved - minimum (always computed live)
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AccountType(StrEnum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"
    CREDIT_CARD = "CREDIT_CARD"
    CASH = "CASH"
    E_WALLET = "E_WALLET"
    OTHER = "OTHER"


class AccountStatus(StrEnum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


class Account(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Sensitive data policy: only a masked account number is ever stored.
    masked_account_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_type: Mapped[AccountType] = mapped_column(
        SAEnum(AccountType), default=AccountType.CHECKING, nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="CNY", nullable=False)

    actual_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )
    balance_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    minimum_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )
    include_in_allocation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        SAEnum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False
    )


class BalanceSource(StrEnum):
    STATEMENT = "STATEMENT"
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"


class AccountBalanceSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A point-in-time record of an account's balances (for trends)."""

    __tablename__ = "account_balance_snapshots"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    available_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    source: Mapped[BalanceSource] = mapped_column(
        SAEnum(BalanceSource), default=BalanceSource.MANUAL, nullable=False
    )
