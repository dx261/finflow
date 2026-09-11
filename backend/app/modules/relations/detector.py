"""Refund / reversal detection.

A credit transaction that returns money from the same counterparty as an
earlier debit (full or partial amount) is a refund or reversal of that
debit. Such transactions must not be counted as income.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.modules.statements.parsers.normalizer import normalize_text


class RelationType(StrEnum):
    REFUND = "REFUND"
    REVERSAL = "REVERSAL"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
    CORRECTION = "CORRECTION"


@dataclass(frozen=True)
class Txn:
    id: str
    account_id: str
    transaction_date: date | None
    amount: Decimal
    direction: str  # "DEBIT" | "CREDIT"
    counterparty_name: str | None


@dataclass(frozen=True)
class RelationCandidate:
    source_transaction_id: str
    target_transaction_id: str
    relation_type: str
    confidence: float
    date_delta_days: int


_WINDOW_DAYS = 30


def _same_counterparty(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return normalize_text(a) == normalize_text(b)


def _confidence(debit: Txn, credit: Txn, delta: int) -> float:
    amount_full = 1.0 if credit.amount == debit.amount else 0.6
    date_near = 1.0 if delta == 0 else 0.8 if delta <= 3 else 0.5 if delta <= 7 else 0.3
    return amount_full * 0.7 + date_near * 0.3


def detect_refund_relations(transactions: list[Txn]) -> list[RelationCandidate]:
    """Pair each refund credit with its originating debit.

    A credit matches a debit when: same account, same counterparty, the
    credit amount does not exceed the debit amount, and the credit is dated
    at or after the debit (within a window). Greedy: each credit binds to
    the earliest qualifying debit at most once.
    """
    debits = sorted(
        (t for t in transactions if t.direction == "DEBIT"),
        key=lambda t: t.transaction_date or date.min,
    )
    credits = [t for t in transactions if t.direction == "CREDIT"]

    candidates: list[RelationCandidate] = []
    used_debits: set[str] = set()

    for credit in credits:
        for debit in debits:
            if debit.id in used_debits:
                continue
            if debit.account_id != credit.account_id:
                continue
            if not _same_counterparty(debit.counterparty_name, credit.counterparty_name):
                continue
            if credit.amount > debit.amount:
                continue
            if debit.transaction_date is None or credit.transaction_date is None:
                continue
            delta = (credit.transaction_date - debit.transaction_date).days
            if delta < 0 or delta > _WINDOW_DAYS:
                continue

            relation_type = (
                RelationType.REVERSAL.value
                if credit.amount == debit.amount and delta <= 3
                else RelationType.REFUND.value
            )
            candidates.append(
                RelationCandidate(
                    source_transaction_id=debit.id,
                    target_transaction_id=credit.id,
                    relation_type=relation_type,
                    confidence=round(_confidence(debit, credit, delta), 3),
                    date_delta_days=delta,
                )
            )
            used_debits.add(debit.id)
            break

    return candidates
