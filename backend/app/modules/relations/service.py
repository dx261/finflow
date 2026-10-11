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
        existing = {
            (source_id, target_id, relation_type)
            for source_id, target_id, relation_type in (
                await self.session.execute(
                    select(
                        TransactionRelation.source_transaction_id,
                        TransactionRelation.target_transaction_id,
                        TransactionRelation.relation_type,
                    ).where(
                        TransactionRelation.source_transaction_id.in_(txns_by_id),
                        TransactionRelation.target_transaction_id.in_(txns_by_id),
                    )
                )
            ).all()
        }
        already_related_sources = {
            source_id
            for source_id, _, relation_type in existing
            if relation_type in (RelationType.REFUND, RelationType.REVERSAL)
        }

        relations: list[TransactionRelation] = []
        for candidate in candidates:
            key = (
                uuid.UUID(candidate.source_transaction_id),
                uuid.UUID(candidate.target_transaction_id),
                RelationType(candidate.relation_type),
            )
            if key in existing or key[0] in already_related_sources:
                continue
            relation = TransactionRelation(
                source_transaction_id=key[0],
                target_transaction_id=key[1],
                relation_type=key[2],
                confidence=candidate.confidence,
            )
            self.session.add(relation)
            relations.append(relation)
            existing.add(key)
            already_related_sources.add(key[0])

            refund_txn = txns_by_id[uuid.UUID(candidate.target_transaction_id)]
            refund_txn.transaction_type = (
                TransactionType.REVERSAL
                if candidate.relation_type == RelationType.REVERSAL.value
                else TransactionType.REFUND
            )

        if relations:
            await self.session.flush()
        return relations
