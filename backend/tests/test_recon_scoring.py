"""Reconciliation scoring tests (§44-46, §96)."""

from datetime import date
from decimal import Decimal

import pytest
from app.modules.reconciliation.scoring import (
    PaymentMatchSide,
    TransactionMatchSide,
    Weights,
    counterparty_score,
    date_score,
    reference_score,
    score_match,
)


def _payment(**overrides) -> PaymentMatchSide:
    defaults = {
        "amount": Decimal("8000.00"),
        "planned_date": date(2026, 9, 5),
        "payee_name": "房东",
        "bank_reference": None,
        "account_id": "acc-a",
    }
    defaults.update(overrides)
    return PaymentMatchSide(**defaults)


def _txn(**overrides) -> TransactionMatchSide:
    defaults = {
        "amount": Decimal("8000.00"),
        "transaction_date": date(2026, 9, 5),
        "counterparty": "房东",
        "reference": None,
        "account_id": "acc-a",
    }
    defaults.update(overrides)
    return TransactionMatchSide(**defaults)


def test_perfect_match_scores_1_0() -> None:
    result = score_match(_payment(), _txn())
    assert result.total == 1.0
    assert result.amount == 1.0
    assert result.account == 1.0
    assert result.date == 1.0
    assert result.counterparty == 1.0


def test_amount_mismatch_dominates() -> None:
    result = score_match(_payment(amount=Decimal("8000.00")), _txn(amount=Decimal("9000.00")))
    # 45% signal lost; everything else perfect.
    assert result.amount == 0.0
    # reference missing -> excluded + renormalized: 0.50/0.95
    assert result.total == pytest.approx(0.5263, abs=1e-3)


def test_date_score_steps() -> None:
    p = date(2026, 9, 5)
    assert date_score(p, date(2026, 9, 5)) == 1.0
    assert date_score(p, date(2026, 9, 6)) == 0.9
    assert date_score(p, date(2026, 9, 8)) == 0.7
    assert date_score(p, date(2026, 9, 15)) == 0.2


def test_counterparty_fuzzy_match() -> None:
    # 房东张三 vs 张三 (subset match) and ZHANG SAN vs zhang san (case/spacing).
    assert counterparty_score("房东张三", "张三") >= 0.6
    assert counterparty_score("ZHANG SAN", "zhang san") >= 0.9
    assert counterparty_score("房东", "完全不相关") < 0.3


def test_counterparty_missing_is_neutral() -> None:
    assert counterparty_score(None, "张三") == 0.5
    assert counterparty_score("房东", None) == 0.5


def test_reference_matching() -> None:
    assert reference_score("REF-1", "REF-1") == 1.0
    assert reference_score("REF-1", "REF-2") == 0.0
    assert reference_score("REF-1", None) == 0.5


def test_account_mismatch() -> None:
    result = score_match(_payment(), _txn(account_id="acc-b"))
    assert result.account == 0.0
    # 0.75 / 0.95 (reference excluded) renormalized.
    assert result.total == pytest.approx(0.7895, abs=1e-3)


def test_custom_weights() -> None:
    weights = Weights(amount=1.0, account=0.0, date=0.0, counterparty=0.0, reference=0.0)
    result = score_match(_payment(amount=Decimal("1")), _txn(amount=Decimal("1")), weights)
    assert result.total == 1.0


def test_plan_example_auto_match() -> None:
    # §96: payment 8000 / account A / Sept 5 vs txn -8000 / account A / Sept 5
    result = score_match(_payment(), _txn())
    assert result.total >= 0.80  # auto-match threshold
