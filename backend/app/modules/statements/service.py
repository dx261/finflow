"""Statement import business logic: upload, parse, normalize, insert."""

import logging
import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BadRequestError,
    DuplicateImportError,
    NotFoundError,
    PayloadTooLargeError,
)
from app.modules.accounts.models import Account
from app.modules.audit.service import AuditService
from app.modules.banks.models import Bank
from app.modules.categories.classifier import classify
from app.modules.categories.models import Category
from app.modules.relations.service import RelationService
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
from app.modules.transfers.service import TransferService

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
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            raise PayloadTooLargeError(
                f"Statement exceeds the {settings.max_upload_size_mb} MB upload limit."
            )

        await self._get_owned_account(user_id, account_id)

        file_hash = self.storage.hash_content(content)
        existing = await self.repository.get_by_hash(account_id, file_hash)
        if existing is not None and not force_import:
            raise DuplicateImportError("This statement file was already imported.")

        stored, _, ext = self.storage.save(filename, content)
        try:
            import_record = await self.repository.create_import(
                account_id=account_id,
                original_filename=filename,
                stored_filename=stored,
                file_hash=file_hash,
                file_type=ext,
            )
            await AuditService(self.session).record(
                user_id=user_id,
                action="STATEMENT_UPLOADED",
                resource_type="statement_import",
                resource_id=str(import_record.id),
                after_data={
                    "account_id": str(account_id),
                    "filename": filename,
                    "forced": existing is not None,
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            self.storage.delete(stored)
            raise
        return UploadResult(
            import_id=import_record.id,
            status=import_record.status,
            is_duplicate=False,
            message=(
                "Forced re-import accepted, processing queued."
                if existing is not None
                else "Upload accepted, processing queued."
            ),
        )

    async def mark_queued(self, import_id: uuid.UUID) -> None:
        record = await self.repository.get_import(import_id)
        if record is None:
            raise NotFoundError("Statement import not found.")
        await self.repository.set_status(record, StatementImportStatus.QUEUED)
        await self.session.commit()

    async def mark_dispatch_failed(self, import_id: uuid.UUID) -> None:
        record = await self.repository.get_import(import_id)
        if record is None:
            return
        await self.repository.create_import_error(
            statement_import_id=import_id,
            row_number=None,
            field=None,
            raw_value=None,
            error_code="QUEUE_UNAVAILABLE",
            message="The background import worker could not be reached.",
        )
        await self.repository.set_status(record, StatementImportStatus.FAILED)
        await self.session.commit()

    async def process_import(self, import_id: uuid.UUID) -> StatementImport:
        """Parse the stored file and insert normalized transactions.

        This is the synchronous core that TASK-014 runs inside a Celery
        task. Safe to call directly (used by tests and fallback paths).
        """
        import_record = await self.repository.get_import_for_update(import_id)
        if import_record is None:
            raise NotFoundError("Statement import not found.")
        if import_record.status in (
            StatementImportStatus.SUCCESS,
            StatementImportStatus.PARTIAL_SUCCESS,
        ):
            return import_record

        await self.repository.set_status(import_record, StatementImportStatus.PARSING)

        account = await self.session.scalar(
            select(Account).where(Account.id == import_record.account_id).with_for_update()
        )
        if account is None:
            raise NotFoundError("Account not found.")
        bank = await self.session.get(Bank, account.bank_id)
        parser = get_parser(bank.statement_parser_type if bank else "GENERIC")

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
        dates: list[date] = []
        balance_candidates: list[tuple[date, int, Decimal]] = []
        category_cache: dict[str, uuid.UUID | None] = {}

        for row_index, (txn, fingerprint) in enumerate(
            zip(transactions, fingerprints, strict=True)
        ):
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
                balance_date = txn.posting_date or txn.transaction_date
                if balance_date is not None:
                    balance_candidates.append((balance_date, row_index, txn.balance_after))

        # Refresh the account only from a statement that is at least as new as
        # the currently known balance.  Bank exports are frequently sorted in
        # descending order, so "the last parsed row" is not necessarily the
        # newest balance.
        incoming_date = statement.statement_date or (max(dates) if dates else None)
        newest_row_balance = (
            max(balance_candidates, key=lambda item: (item[0], item[1]))[2]
            if balance_candidates
            else None
        )
        incoming_balance = (
            statement.balance if statement.balance is not None else newest_row_balance
        )
        balance_updated = False
        if incoming_date is not None and incoming_balance is not None:
            incoming_as_of = datetime.combine(incoming_date, time.min, tzinfo=UTC)
            current_as_of = account.balance_as_of
            if current_as_of is not None and current_as_of.tzinfo is None:
                current_as_of = current_as_of.replace(tzinfo=UTC)
            if current_as_of is None or incoming_as_of >= current_as_of:
                account.actual_balance = incoming_balance
                account.balance_as_of = incoming_as_of
                balance_updated = True

        reservation_shortfall = None
        if balance_updated:
            # Existing reservations remain intact, but a newly imported lower
            # balance must be surfaced as an operational exception instead of
            # silently producing an unexplained negative planning balance.
            from app.modules.allocation.service import sum_reserved_amount

            reserved = await sum_reserved_amount(self.session, account.id)
            planning_available = account.actual_balance - reserved - account.minimum_balance
            if planning_available < 0:
                reservation_shortfall = abs(planning_available)
                await AuditService(self.session).record(
                    user_id=account.user_id,
                    action="RESERVATION_SHORTFALL_DETECTED",
                    resource_type="account",
                    resource_id=str(account.id),
                    after_data={
                        "shortfall": str(reservation_shortfall),
                        "balance_as_of": incoming_as_of.isoformat(),
                    },
                )

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
        # Persist transaction semantics as part of the same import
        # transaction, so downstream reports never briefly see unclassified
        # transfers/refunds.
        await self.session.flush()
        await RelationService(self.session).apply_for_account(account.id)
        await TransferService(self.session).apply_for_user(account.user_id)
        await AuditService(self.session).record(
            user_id=account.user_id,
            action="STATEMENT_IMPORT_COMPLETED",
            resource_type="statement_import",
            resource_id=str(import_record.id),
            after_data={
                "inserted": inserted,
                "skipped": skipped,
                "status": status.value,
                "balance_updated": balance_updated,
                "reservation_shortfall": (
                    str(reservation_shortfall) if reservation_shortfall is not None else None
                ),
            },
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
