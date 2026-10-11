"""Statement import and transaction models."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StatementImportStatus(StrEnum):
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TransactionDirection(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class TransactionType(StrEnum):
    NORMAL = "NORMAL"
    REFUND = "REFUND"
    REVERSAL = "REVERSAL"
    TRANSFER = "TRANSFER"
    FEE = "FEE"
    INTEREST = "INTEREST"


class ReconciliationStatus(StrEnum):
    UNMATCHED = "UNMATCHED"
    MATCHED = "MATCHED"


class StatementImport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One uploaded statement file and its processing state."""

    __tablename__ = "statement_imports"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[StatementImportStatus] = mapped_column(
        SAEnum(StatementImportStatus), default=StatementImportStatus.UPLOADED, nullable=False
    )
    statement_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    statement_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    success_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    failed_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A normalized bank transaction."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_transactions_amount_nonnegative"),
        UniqueConstraint("account_id", "fingerprint", name="uq_transactions_account_fingerprint"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    statement_import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("statement_imports.id", ondelete="CASCADE"), index=True, nullable=False
    )

    external_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transaction_date: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)
    posting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    direction: Mapped[TransactionDirection] = mapped_column(
        SAEnum(TransactionDirection), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CNY", nullable=False)

    counterparty_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counterparty_account_masked: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True, nullable=True
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType), default=TransactionType.NORMAL, nullable=False
    )
    reconciliation_status: Mapped[ReconciliationStatus] = mapped_column(
        SAEnum(ReconciliationStatus),
        default=ReconciliationStatus.UNMATCHED,
        nullable=False,
    )
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)


class ImportError(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A row that failed during import (partial imports stay usable)."""

    __tablename__ = "import_errors"

    statement_import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("statement_imports.id", ondelete="CASCADE"), index=True, nullable=False
    )
    row_number: Mapped[int | None] = mapped_column(nullable=True)
    field: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_code: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
