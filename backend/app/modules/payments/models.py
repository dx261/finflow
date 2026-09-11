"""Payment plan model."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PaymentStatus(StrEnum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    ALLOCATED = "ALLOCATED"
    RESERVED = "RESERVED"
    WAITING_MANUAL_EXECUTION = "WAITING_MANUAL_EXECUTION"
    MANUALLY_EXECUTED = "MANUALLY_EXECUTED"
    RECONCILING = "RECONCILING"
    SETTLED = "SETTLED"
    EXCEPTION = "EXCEPTION"
    CANCELLED = "CANCELLED"


class PaymentPriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class PaymentPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A planned future payment the user intends to make manually."""

    __tablename__ = "payment_plans"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payee_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CNY", nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)

    priority: Mapped[PaymentPriority] = mapped_column(
        SAEnum(PaymentPriority), default=PaymentPriority.NORMAL, nullable=False
    )
    preferred_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), index=True, nullable=True
    )

    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus), default=PaymentStatus.DRAFT, nullable=False
    )

    # Manual execution record (filled by the user after paying at the bank).
    manual_execution_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    manual_execution_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    manual_execution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Idempotency key for recurring generation: a plan created by a
    # recurring payment for a specific occurrence date.
    source_recurring_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recurring_payments.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    occurrence_date: Mapped[date | None] = mapped_column(Date, nullable=True)
