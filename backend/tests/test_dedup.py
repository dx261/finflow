"""Transaction fingerprint tests."""

from datetime import date
from decimal import Decimal

from app.modules.statements.dedup import compute_fingerprint, transaction_fingerprint
from app.modules.statements.parsers.base import Direction, ParsedTransaction


def _fp(
    *,
    account: str = "acc-1",
    day: date = date(2026, 9, 1),
    amount: Decimal = Decimal("100.00"),
    direction: str = "DEBIT",
    description: str = "coffee",
    reference: str | None = None,
) -> str:
    return compute_fingerprint(
        account_id=account,
        transaction_date=day,
        amount=amount,
        direction=direction,
        description=description,
        external_reference=reference,
    )


def test_same_fields_same_fingerprint() -> None:
    assert _fp() == _fp()


def test_amount_change_changes_fingerprint() -> None:
    assert _fp() != _fp(amount=Decimal("101.00"))


def test_date_change_changes_fingerprint() -> None:
    assert _fp() != _fp(day=date(2026, 9, 2))


def test_description_change_changes_fingerprint() -> None:
    # Same amount+date but different description must NOT dedupe together.
    assert _fp() != _fp(description="tea")


def test_direction_change_changes_fingerprint() -> None:
    assert _fp() != _fp(direction="CREDIT")


def test_account_change_changes_fingerprint() -> None:
    assert _fp() != _fp(account="acc-2")


def test_whitespace_and_case_insensitive() -> None:
    assert _fp(description="  COFFEE ") == _fp(description="coffee")


def test_reference_included() -> None:
    assert _fp() != _fp(reference="REF123")


def test_missing_date_and_reference() -> None:
    fp = _fp(day=None, reference=None)
    assert fp == _fp(day=None, reference=None)


def test_parsed_transaction_fingerprint() -> None:
    txn = ParsedTransaction(
        transaction_date=date(2026, 9, 1),
        description="房租",
        amount=Decimal("8000.00"),
        direction=Direction.DEBIT,
        reference="R-9",
    )
    assert transaction_fingerprint("acc-x", txn) == compute_fingerprint(
        account_id="acc-x",
        transaction_date=date(2026, 9, 1),
        amount=Decimal("8000.00"),
        direction="DEBIT",
        description="房租",
        external_reference="R-9",
    )
