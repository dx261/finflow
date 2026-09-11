"""Transaction relation persistence."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.relations.detector import Txn as DetectorTxn
from app.modules.relations.detector import detect_refund_relations
from app.modules.relations.models import RelationType, TransactionRelation
from app.modules.statements.models import Transaction, TransactionType


def _to_detector_txn(txn: Transaction) -> DetectorTxn:
    return DetectorTxn(
        id=str(txn.id),
        account_id=str(txn.account_id),
        transaction_date=txn.transaction_date,
        amount=txn.amount,
        direction=txn.direction.value,
        counterparty_name=txn.counterparty_name,
    )


class RelationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def apply_for_account(self, account_id: uuid.UUID) -> list[TransactionRelation]:
        """Detect and persist refund/reversal relations for an account."""
        txns = list(
            await self.session.scalars(
                select(Transaction).where(Transaction.account_id == account_id)
            )
        )
        txns_by_id = {txn.id: txn for txn in txns}
        candidates = detect_refund_relations([_to_detector_txn(t) for t in txns])

        relations: list[TransactionRelation] = []
        for candidate in candidates:
            relation = TransactionRelation(
                source_transaction_id=uuid.UUID(candidate.source_transaction_id),
                target_transaction_id=uuid.UUID(candidate.target_transaction_id),
                relation_type=RelationType(candidate.relation_type),
                confidence=candidate.confidence,
            )
            self.session.add(relation)
            relations.append(relation)

            refund_txn = txns_by_id[uuid.UUID(candidate.target_transaction_id)]
            refund_txn.transaction_type = (
                TransactionType.REVERSAL
                if candidate.relation_type == RelationType.REVERSAL.value
                else TransactionType.REFUND
            )

        if relations:
            await self.session.commit()
        return relations
