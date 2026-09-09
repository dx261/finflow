"""Internal transfer detection.

A debit of ¥5,000 in account A and a credit of ¥5,000 in account B, close
in time, is an internal transfer between the user's own accounts. Such
transactions must NOT be counted as income/expense.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Txn:
    """Minimal transaction view used by the matcher."""

    id: str
    account_id: str
    transaction_date: date
    amount: Decimal
    direction: str  # "DEBIT" | "CREDIT"


@dataclass(frozen=True)
class TransferMatch:
    debit: Txn
    credit: Txn
    confidence: float
    date_delta_days: int


_AMOUNT_TOLERANCE = Decimal("0.01")


def _date_score(delta_days: int) -> float:
    if delta_days == 0:
        return 1.0
    if delta_days <= 1:
        return 0.9
    if delta_days <= 3:
        return 0.7
    if delta_days <= 7:
        return 0.3
    return 0.0


def detect_internal_transfers(
    transactions: list[Txn],
    *,
    window_days: int = 7,
    min_confidence: float = 0.7,
) -> list[TransferMatch]:
    """Pair debits and credits across different accounts.

    A candidate requires an equal amount (within tolerance), a date gap
    within ``window_days`` and two distinct owned accounts. Candidates are
    scored and greedily matched so each transaction pairs at most once.
    """
    debits = [t for t in transactions if t.direction == "DEBIT"]
    credits = [t for t in transactions if t.direction == "CREDIT"]

    candidates: list[TransferMatch] = []
    for debit in debits:
        for credit in credits:
            if debit.account_id == credit.account_id:
                continue
            # Compare absolute magnitudes — a debit is often stored signed.
            if abs(abs(debit.amount) - abs(credit.amount)) > _AMOUNT_TOLERANCE:
                continue
            delta = abs((debit.transaction_date - credit.transaction_date).days)
            if delta > window_days:
                continue
            # Amount equality is the strongest signal (weight 0.6); date
            # proximity is secondary (weight 0.4).
            confidence = 0.6 * 1.0 + 0.4 * _date_score(delta)
            candidates.append(TransferMatch(debit, credit, confidence, delta))

    candidates.sort(key=lambda m: (-m.confidence, m.date_delta_days))
    matches: list[TransferMatch] = []
    used_debits: set[str] = set()
    used_credits: set[str] = set()
    for match in candidates:
        if match.confidence < min_confidence:
            continue
        if match.debit.id in used_debits or match.credit.id in used_credits:
            continue
        used_debits.add(match.debit.id)
        used_credits.add(match.credit.id)
        matches.append(match)
    return matches
