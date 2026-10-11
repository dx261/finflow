"""Persist internal-transfer relationships after statement imports."""

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.models import Account
from app.modules.relations.models import RelationType, TransactionRelation
from app.modules.statements.models import Transaction, TransactionType
from app.modules.transfers.detector import Txn, detect_internal_transfers


class TransferService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def apply_for_user(self, user_id: uuid.UUID) -> list[TransactionRelation]:
        if self.session.get_bind().dialect.name == "postgresql":
            # Imports for different accounts can finish concurrently.  Keep
            # transfer pairing one-to-one by serializing detection per owner.
            await self.session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:user_id))"),
                {"user_id": str(user_id)},
            )
        account_ids = list(
            await self.session.scalars(select(Account.id).where(Account.user_id == user_id))
        )
        if len(account_ids) < 2:
            return []
        transactions = list(
            await self.session.scalars(
                select(Transaction).where(
                    Transaction.account_id.in_(account_ids),
                    Transaction.transaction_date.is_not(None),
                )
            )
        )
        by_id = {transaction.id: transaction for transaction in transactions}
        existing = {
            (source_id, target_id)
            for source_id, target_id in (
                await self.session.execute(
                    select(
                        TransactionRelation.source_transaction_id,
                        TransactionRelation.target_transaction_id,
                    ).where(
                        TransactionRelation.relation_type == RelationType.INTERNAL_TRANSFER,
                        TransactionRelation.source_transaction_id.in_(by_id),
                        TransactionRelation.target_transaction_id.in_(by_id),
                    )
                )
            ).all()
        }
        already_linked = {transaction_id for pair in existing for transaction_id in pair}
        detector_rows = [
            Txn(
                id=str(transaction.id),
                account_id=str(transaction.account_id),
                transaction_date=transaction.transaction_date,
                amount=transaction.amount,
                direction=transaction.direction.value,
            )
            for transaction in transactions
            if transaction.transaction_date is not None and transaction.id not in already_linked
        ]
        matches = detect_internal_transfers(detector_rows)
        created: list[TransactionRelation] = []
        for match in matches:
            key = (uuid.UUID(match.debit.id), uuid.UUID(match.credit.id))
            if key in existing:
                continue
            relation = TransactionRelation(
                source_transaction_id=key[0],
                target_transaction_id=key[1],
                relation_type=RelationType.INTERNAL_TRANSFER,
                confidence=match.confidence,
            )
            self.session.add(relation)
            created.append(relation)
            existing.add(key)
            already_linked.update(key)
            by_id[key[0]].transaction_type = TransactionType.TRANSFER
            by_id[key[1]].transaction_type = TransactionType.TRANSFER
        if created:
            await self.session.flush()
        return created
