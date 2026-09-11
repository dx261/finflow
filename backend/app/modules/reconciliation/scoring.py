"""Reconciliation matching score (§42-46).

A payment is matched against a candidate bank transaction across five
signals. Weights are configurable (CODING_PLAN.md §43 forbids hardcoding);
defaults live in settings.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from rapidfuzz import fuzz

from app.core.config import settings


@dataclass(frozen=True)
class Weights:
    amount: float = 0.45
    account: float = 0.20
    date: float = 0.15
    counterparty: float = 0.15
    reference: float = 0.05

    @classmethod
    def from_settings(cls) -> "Weights":
        return cls(
            amount=settings.recon_amount_weight,
            account=settings.recon_account_weight,
            date=settings.recon_date_weight,
            counterparty=settings.recon_counterparty_weight,
            reference=settings.recon_reference_weight,
        )


@dataclass(frozen=True)
class PaymentMatchSide:
    amount: Decimal
    planned_date: date
    payee_name: str | None
    bank_reference: str | None
    account_id: str


@dataclass(frozen=True)
class TransactionMatchSide:
    amount: Decimal
    transaction_date: date
    counterparty: str | None
    reference: str | None
    account_id: str


@dataclass(frozen=True)
class ScoreResult:
    total: float
    amount: float
    account: float
    date: float
    counterparty: float
    reference: float


def amount_score(payment_amount: Decimal, txn_amount: Decimal) -> float:
    """Amount is the strongest signal: exact equality scores 1.0, else 0.0."""
    return 1.0 if payment_amount == txn_amount else 0.0


def account_score(payment_account_id: str, txn_account_id: str) -> float:
    return 1.0 if payment_account_id == txn_account_id else 0.0


def date_score(payment_date: date, txn_date: date) -> float:
    delta = abs((payment_date - txn_date).days)
    if delta == 0:
        return 1.0
    if delta <= 1:
        return 0.9
    if delta <= 3:
        return 0.7
    if delta <= 7:
        return 0.4
    return 0.2


def counterparty_score(payee_name: str | None, counterparty: str | None) -> float:
    """Fuzzy text similarity, tolerant of case and extra words
    (房东张三 vs 张三 vs ZHANG SAN)."""
    if not payee_name or not counterparty:
        return 0.5  # neutral — no evidence either way
    a = payee_name.lower()
    b = counterparty.lower()
    best = max(fuzz.ratio(a, b), fuzz.token_set_ratio(a, b))
    return best / 100.0


def reference_score(payment_reference: str | None, txn_reference: str | None) -> float:
    if payment_reference and txn_reference:
        return 1.0 if payment_reference == txn_reference else 0.0
    return 0.5  # neutral — missing on one side


def score_match(
    payment: PaymentMatchSide,
    txn: TransactionMatchSide,
    weights: Weights | None = None,
) -> ScoreResult:
    """Compute the weighted match score between a payment and a transaction."""
    w = weights or Weights.from_settings()

    amount = amount_score(payment.amount, txn.amount)
    account = account_score(payment.account_id, txn.account_id)
    date = date_score(payment.planned_date, txn.transaction_date)
    counterparty = counterparty_score(payment.payee_name, txn.counterparty)
    reference = reference_score(payment.bank_reference, txn.reference)

    # Signals with no evidence on either side are excluded and the
    # remaining weights renormalized, so a perfect match scores 1.0.
    present: list[tuple[float, float]] = [
        (w.amount, amount),
        (w.account, account),
        (w.date, date),
    ]
    if payment.payee_name and txn.counterparty:
        present.append((w.counterparty, counterparty))
    if payment.bank_reference and txn.reference:
        present.append((w.reference, reference))

    weight_sum = sum(weight for weight, _ in present)
    total = sum(weight * score for weight, score in present) / weight_sum
    return ScoreResult(
        total=total,
        amount=amount,
        account=account,
        date=date,
        counterparty=counterparty,
        reference=reference,
    )
