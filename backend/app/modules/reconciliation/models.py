"""Reconciliation model."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Float, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReconStatus(StrEnum):
    AUTO_MATCHED = "AUTO_MATCHED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class Reconciliation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A proposed or confirmed match between a payment and a transaction."""

    __tablename__ = "reconciliations"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), index=True, nullable=False
    )

    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    amount_score: Mapped[float] = mapped_column(Float, nullable=False)
    account_score: Mapped[float] = mapped_column(Float, nullable=False)
    date_score: Mapped[float] = mapped_column(Float, nullable=False)
    counterparty_score: Mapped[float] = mapped_column(Float, nullable=False)
    reference_score: Mapped[float] = mapped_column(Float, nullable=False)

    status: Mapped[ReconStatus] = mapped_column(
        SAEnum(ReconStatus), default=ReconStatus.REVIEW_REQUIRED, nullable=False
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
