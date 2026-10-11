"""Cash flow plan model (§57)."""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CashFlowPlanType(StrEnum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class CashFlowPlanStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CashFlowPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A scheduled future income or expense (not tied to a PaymentPlan)."""

    __tablename__ = "cash_flow_plans"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_cash_flow_plans_amount_positive"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=True
    )
    type: Mapped[CashFlowPlanType] = mapped_column(SAEnum(CashFlowPlanType), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CNY", nullable=False)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    status: Mapped[CashFlowPlanStatus] = mapped_column(
        SAEnum(CashFlowPlanStatus), default=CashFlowPlanStatus.ACTIVE, nullable=False
    )
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
