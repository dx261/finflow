"""Internal transfer detection tests."""

from datetime import date, timedelta
from decimal import Decimal

from app.modules.transfers.detector import Txn, detect_internal_transfers


def _txn(
    id: str,
    account: str,
    day: date,
    amount: str,
    direction: str,
) -> Txn:
    return Txn(
        id=id,
        account_id=account,
        transaction_date=day,
        amount=Decimal(amount),
        direction=direction,
    )


DAY = date(2026, 9, 5)


def test_same_amount_same_day_different_accounts() -> None:
    txns = [
        _txn("out-1", "A", DAY, "-5000", "DEBIT"),
        _txn("in-1", "B", DAY, "5000", "CREDIT"),
    ]
    matches = detect_internal_transfers(txns)
    assert len(matches) == 1
    assert matches[0].debit.id == "out-1"
    assert matches[0].credit.id == "in-1"
    assert matches[0].confidence == 1.0


def test_plan_scenario() -> None:
    # A -5000 / B +5000 within one day -> INTERNAL_TRANSFER.
    txns = [
        _txn("a-1", "A", DAY, "-5000", "DEBIT"),
        _txn("b-1", "B", DAY + timedelta(days=1), "5000", "CREDIT"),
    ]
    matches = detect_internal_transfers(txns)
    assert len(matches) == 1
    # amount(1.0)*0.6 + date(0.9)*0.4 = 0.96
    assert matches[0].confidence == 0.96


def test_same_account_is_not_a_transfer() -> None:
    txns = [
        _txn("d-1", "A", DAY, "-5000", "DEBIT"),
        _txn("c-1", "A", DAY, "5000", "CREDIT"),
    ]
    assert detect_internal_transfers(txns) == []


def test_different_amounts_not_matched() -> None:
    txns = [
        _txn("d-1", "A", DAY, "-5000", "DEBIT"),
        _txn("c-1", "B", DAY, "5001", "CREDIT"),
    ]
    assert detect_internal_transfers(txns) == []


def test_amount_tolerance_allows_rounding() -> None:
    txns = [
        _txn("d-1", "A", DAY, "-5000.00", "DEBIT"),
        _txn("c-1", "B", DAY, "5000.005", "CREDIT"),
    ]
    matches = detect_internal_transfers(txns)
    assert len(matches) == 1


def test_too_far_apart_in_time_not_matched() -> None:
    txns = [
        _txn("d-1", "A", DAY, "-5000", "DEBIT"),
        _txn("c-1", "B", DAY + timedelta(days=30), "5000", "CREDIT"),
    ]
    assert detect_internal_transfers(txns) == []


def test_greedy_matching_pairs_best() -> None:
    # Two credits for one debit; the closer one should win.
    txns = [
        _txn("d-1", "A", DAY, "-5000", "DEBIT"),
        _txn("c-close", "B", DAY, "5000", "CREDIT"),
        _txn("c-far", "C", DAY + timedelta(days=6), "5000", "CREDIT"),
    ]
    matches = detect_internal_transfers(txns)
    assert len(matches) == 1
    assert matches[0].credit.id == "c-close"


def test_transactions_paired_at_most_once() -> None:
    txns = [
        _txn("d-1", "A", DAY, "-5000", "DEBIT"),
        _txn("d-2", "A", DAY, "-5000", "DEBIT"),
        _txn("c-1", "B", DAY, "5000", "CREDIT"),
    ]
    matches = detect_internal_transfers(txns)
    # One credit can match at most one debit.
    assert len(matches) == 1


def test_income_and_expense_not_collapsed() -> None:
    # Same account direction pairs must never be considered transfers.
    txns = [
        _txn("d-1", "A", DAY, "-5000", "DEBIT"),
        _txn("c-1", "A", DAY, "5000", "CREDIT"),
    ]
    assert detect_internal_transfers(txns) == []
