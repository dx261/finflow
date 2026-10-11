"""Fund allocation model.

A FundAllocation ties part of a payment to a funding account. Its lifecycle
mirrors the payment: proposed in a preview, reserved on confirmation,
released when the reservation is cancelled, settled once the payment is
reconciled. ``RESERVED`` allocations are a *virtual* reservation — real
bank funds are never frozen.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AllocationStatus(StrEnum):
    PROPOSED = "PROPOSED"
    RESERVED = "RESERVED"
    RELEASED = "RELEASED"
    SETTLED = "SETTLED"


class FundAllocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fund_allocations"
    __table_args__ = (
        CheckConstraint("allocated_amount > 0", name="ck_fund_allocations_amount_positive"),
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[AllocationStatus] = mapped_column(
        SAEnum(AllocationStatus), default=AllocationStatus.PROPOSED, nullable=False
    )
    algorithm_version: Mapped[str] = mapped_column(String(20), default="v1", nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
