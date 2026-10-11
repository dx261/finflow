"""Statement import data access."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.statements.models import (
    ImportError,
    ReconciliationStatus,
    StatementImport,
    StatementImportStatus,
    Transaction,
    TransactionDirection,
    TransactionType,
)


class StatementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Imports -----------------------------------------------------------

    async def create_import(
        self,
        account_id: uuid.UUID,
        original_filename: str,
        stored_filename: str,
        file_hash: str,
        file_type: str,
    ) -> StatementImport:
        record = StatementImport(
            account_id=account_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_hash=file_hash,
            file_type=file_type,
            status=StatementImportStatus.UPLOADED,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_import(self, import_id: uuid.UUID) -> StatementImport | None:
        return await self.session.get(StatementImport, import_id)

    async def get_import_for_update(self, import_id: uuid.UUID) -> StatementImport | None:
        return await self.session.scalar(
            select(StatementImport).where(StatementImport.id == import_id).with_for_update()
        )

    async def list_imports(self, account_id: uuid.UUID) -> list[StatementImport]:
        result = await self.session.scalars(
            select(StatementImport)
            .where(StatementImport.account_id == account_id)
            .order_by(StatementImport.created_at.desc())
        )
        return list(result)

    async def get_by_hash(self, account_id: uuid.UUID, file_hash: str) -> StatementImport | None:
        result = await self.session.scalar(
            select(StatementImport).where(
                StatementImport.account_id == account_id,
                StatementImport.file_hash == file_hash,
            )
        )
        return result

    async def update_import_result(
        self,
        import_record: StatementImport,
        *,
        status: StatementImportStatus,
        total_rows: int,
        success_rows: int,
        failed_rows: int,
        start_date: date | None,
        end_date: date | None,
        completed_at: object,
    ) -> StatementImport:
        import_record.status = status
        import_record.total_rows = total_rows
        import_record.success_rows = success_rows
        import_record.failed_rows = failed_rows
        import_record.statement_start_date = start_date
        import_record.statement_end_date = end_date
        import_record.completed_at = completed_at  # type: ignore[assignment]
        await self.session.flush()
        return import_record

    async def set_status(
        self, import_record: StatementImport, status: StatementImportStatus
    ) -> None:
        import_record.status = status
        await self.session.flush()

    # --- Transactions --------------------------------------------------------

    async def existing_fingerprints(
        self, account_id: uuid.UUID, fingerprints: list[str]
    ) -> set[str]:
        result = await self.session.scalars(
            select(Transaction.fingerprint).where(
                Transaction.account_id == account_id,
                Transaction.fingerprint.in_(fingerprints),
            )
        )
        return set(result)

    async def create_transaction(
        self,
        *,
        account_id: uuid.UUID,
        statement_import_id: uuid.UUID,
        external_reference: str | None,
        transaction_date: date | None,
        posting_date: date | None,
        direction: TransactionDirection,
        amount: Decimal,
        currency: str,
        counterparty_name: str | None,
        counterparty_account_masked: str | None,
        description: str,
        balance_after: Decimal | None,
        category_id: uuid.UUID | None,
        transaction_type: TransactionType,
        raw_data: dict | None,
        fingerprint: str,
    ) -> Transaction:
        txn = Transaction(
            account_id=account_id,
            statement_import_id=statement_import_id,
            external_reference=external_reference,
            transaction_date=transaction_date,
            posting_date=posting_date,
            direction=direction,
            amount=amount,
            currency=currency,
            counterparty_name=counterparty_name,
            counterparty_account_masked=counterparty_account_masked,
            description=description,
            balance_after=balance_after,
            category_id=category_id,
            transaction_type=transaction_type,
            reconciliation_status=ReconciliationStatus.UNMATCHED,
            raw_data=raw_data,
            fingerprint=fingerprint,
        )
        self.session.add(txn)
        return txn

    # --- Errors ---------------------------------------------------------------

    async def create_import_error(
        self,
        *,
        statement_import_id: uuid.UUID,
        row_number: int | None,
        field: str | None,
        raw_value: str | None,
        error_code: str,
        message: str,
    ) -> ImportError:
        error = ImportError(
            statement_import_id=statement_import_id,
            row_number=row_number,
            field=field,
            raw_value=raw_value,
            error_code=error_code,
            message=message,
        )
        self.session.add(error)
        return error

    async def list_errors(self, import_id: uuid.UUID) -> list[ImportError]:
        result = await self.session.scalars(
            select(ImportError)
            .where(ImportError.statement_import_id == import_id)
            .order_by(ImportError.row_number)
        )
        return list(result)
