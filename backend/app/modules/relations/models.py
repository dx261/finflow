"""Transaction relation model."""

import uuid
from enum import StrEnum

from sqlalchemy import CheckConstraint, Float, ForeignKey, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RelationType(StrEnum):
    REFUND = "REFUND"
    REVERSAL = "REVERSAL"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
    CORRECTION = "CORRECTION"


class TransactionRelation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Links a transaction to another it reverses or refunds."""

    __tablename__ = "transaction_relations"
    __table_args__ = (
        CheckConstraint(
            "source_transaction_id <> target_transaction_id",
            name="ck_transaction_relations_distinct_transactions",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_transaction_relations_confidence_range",
        ),
        UniqueConstraint(
            "source_transaction_id",
            "target_transaction_id",
            "relation_type",
            name="uq_transaction_relations_pair_type",
        ),
    )

    source_transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    relation_type: Mapped[RelationType] = mapped_column(SAEnum(RelationType), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
