"""Statement import business logic: upload, parse, normalize, insert."""

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestError,
    DuplicateImportError,
    NotFoundError,
)
from app.modules.accounts.models import Account
from app.modules.banks.models import Bank
from app.modules.categories.classifier import classify
from app.modules.categories.models import Category
from app.modules.statements.dedup import compute_fingerprint
from app.modules.statements.models import (
    StatementImport,
    StatementImportStatus,
    TransactionDirection,
    TransactionType,
)
from app.modules.statements.parsers.base import ParsedStatement
from app.modules.statements.parsers.factory import get_parser
from app.modules.statements.parsers.generic import StatementFile
from app.modules.statements.repository import StatementRepository
from app.modules.statements.schemas import UploadResult
from app.modules.statements.storage import StatementStorage

logger = logging.getLogger("finflow")

_ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}


class StatementService:
    def __init__(self, session: AsyncSession, storage: StatementStorage | None = None) -> None:
        self.session = session
        self.storage = storage or StatementStorage()
        self.repository = StatementRepository(session)

    async def _get_owned_account(self, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
        account = await self.session.get(Account, account_id)
        if account is None or account.user_id != user_id:
            raise NotFoundError("Account not found.")
        return account

    async def upload(
        self,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        filename: str,
        content: bytes,
        force_import: bool = False,
    ) -> UploadResult:
        """Validate, deduplicate and stage an uploaded statement file."""
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in _ALLOWED_EXTENSIONS:
            raise BadRequestError(f"Unsupported file type: .{extension}")

        await self._get_owned_account(user_id, account_id)

        stored, file_hash, ext = self.storage.save(filename, content)
        existing = await self.repository.get_by_hash(account_id, file_hash)
        if existing is not None:
            if not force_import:
                raise DuplicateImportError("This statement file was already imported.")
            return UploadResult(
                import_id=existing.id,
                status=existing.status,
                is_duplicate=True,
                message="Duplicate upload accepted with force_import.",
            )

        import_record = await self.repository.create_import(
            account_id=account_id,
            original_filename=filename,
            stored_filename=stored,
            file_hash=file_hash,
            file_type=ext,
        )
        await self.session.commit()
        return UploadResult(
            import_id=import_record.id,
            status=import_record.status,
            is_duplicate=False,
            message="Upload accepted, processing queued.",
        )

    async def process_import(self, import_id: uuid.UUID) -> StatementImport:
        """Parse the stored file and insert normalized transactions.

        This is the synchronous core that TASK-014 runs inside a Celery
        task. Safe to call directly (used by tests and fallback paths).
        """
        import_record = await self.repository.get_import(import_id)
        if import_record is None:
            raise NotFoundError("Statement import not found.")

        await self.repository.set_status(import_record, StatementImportStatus.PARSING)

        account = await self.session.get(Account, import_record.account_id)
        if account is None:
            raise NotFoundError("Account not found.")
        bank = await self.session.get(Bank, account.bank_id)
        parser = get_parser(bank.code if bank else "GENERIC")

        try:
            path = self.storage.path_for(import_record.stored_filename)
            parsed = parser.parse(StatementFile(path))
        except Exception as exc:
            logger.warning("statement_parse_failed", extra={"import_id": str(import_id)})
            await self.repository.create_import_error(
                statement_import_id=import_id,
                row_number=None,
                field=None,
                raw_value=None,
                error_code="PARSE_FAILED",
                message=str(exc),
            )
            await self.repository.set_status(import_record, StatementImportStatus.FAILED)
            await self.session.commit()
            raise

        return await self._persist(account, bank, import_record, parsed)

    async def _persist(
        self,
        account: Account,
        bank: Bank | None,
        import_record: StatementImport,
        statement: ParsedStatement,
    ) -> StatementImport:
        transactions = statement.transactions

        fingerprints = [
            compute_fingerprint(
                account_id=str(account.id),
                transaction_date=t.transaction_date,
                amount=t.amount,
                direction=t.direction.value if t.direction else "",
                description=t.description,
                external_reference=t.reference,
            )
            for t in transactions
        ]
        existing = await self.repository.existing_fingerprints(account.id, fingerprints)

        inserted = 0
        skipped = 0
        dates: list = []
        last_balance = None
        category_cache: dict[str, uuid.UUID | None] = {}

        for txn, fingerprint in zip(transactions, fingerprints, strict=True):
            if txn.direction is None:
                skipped += 1
                await self.repository.create_import_error(
                    statement_import_id=import_record.id,
                    row_number=None,
                    field="direction",
                    raw_value=txn.description,
                    error_code="MISSING_DIRECTION",
                    message="Transaction has no debit/credit direction.",
                )
                continue
            if fingerprint in existing:
                skipped += 1
                await self.repository.create_import_error(
                    statement_import_id=import_record.id,
                    row_number=None,
                    field="fingerprint",
                    raw_value=txn.description,
                    error_code="DUPLICATE",
                    message="Transaction already exists for this account.",
                )
                continue
            existing.add(fingerprint)

            category_id = await self._category_id(
                txn.description, txn.counterparty_name, category_cache
            )
            await self.repository.create_transaction(
                account_id=account.id,
                statement_import_id=import_record.id,
                external_reference=txn.reference,
                transaction_date=txn.transaction_date,
                posting_date=txn.posting_date,
                direction=TransactionDirection(txn.direction.value),
                amount=txn.amount,
                currency=account.currency,
                counterparty_name=txn.counterparty_name,
                counterparty_account_masked=None,
                description=txn.description,
                balance_after=txn.balance_after,
                category_id=category_id,
                transaction_type=TransactionType.NORMAL,
                raw_data=txn.raw_data,
                fingerprint=fingerprint,
            )
            inserted += 1
            if txn.transaction_date is not None:
                dates.append(txn.transaction_date)
            if txn.balance_after is not None:
                last_balance = txn.balance_after

        # Refresh the account's actual balance from the statement.
        if statement.balance is not None:
            account.actual_balance = statement.balance
            account.balance_as_of = max(dates) if dates else account.balance_as_of
        elif last_balance is not None:
            account.actual_balance = last_balance
            account.balance_as_of = max(dates) if dates else account.balance_as_of

        status = StatementImportStatus.PARTIAL_SUCCESS if skipped else StatementImportStatus.SUCCESS
        await self.repository.update_import_result(
            import_record,
            status=status,
            total_rows=len(transactions),
            success_rows=inserted,
            failed_rows=skipped,
            start_date=min(dates) if dates else None,
            end_date=max(dates) if dates else None,
            completed_at=datetime.now(UTC),
        )
        await self.session.commit()
        logger.info(
            "statement_import_completed",
            extra={"import_id": str(import_record.id), "inserted": inserted, "skipped": skipped},
        )
        return import_record

    async def _category_id(
        self,
        description: str,
        counterparty: str | None,
        cache: dict[str, uuid.UUID | None],
    ) -> uuid.UUID | None:
        code = classify(description=description, counterparty=counterparty)
        if code.value in cache:
            return cache[code.value]
        row = await self.session.scalar(select(Category).where(Category.code == code.value))
        category_id = row.id if row is not None else None
        cache[code.value] = category_id
        return category_id

    async def get_import_for_user(
        self, user_id: uuid.UUID, import_id: uuid.UUID
    ) -> StatementImport:
        record = await self.repository.get_import(import_id)
        if record is None:
            raise NotFoundError("Statement import not found.")
        await self._get_owned_account(user_id, record.account_id)
        return record

    async def list_imports_for_user(
        self, user_id: uuid.UUID, account_id: uuid.UUID
    ) -> list[StatementImport]:
        await self._get_owned_account(user_id, account_id)
        return await self.repository.list_imports(account_id)
