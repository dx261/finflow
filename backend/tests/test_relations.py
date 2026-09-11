"""Refund/reversal relation tests."""

from datetime import date
from decimal import Decimal

from app.modules.relations.detector import (
    RelationCandidate,
    RelationType,
    Txn,
    detect_refund_relations,
)


def _txn(
    tid: str,
    *,
    account: str = "a",
    day: date = date(2026, 9, 1),
    amount: str = "100.00",
    direction: str = "DEBIT",
    counterparty: str = "商户",
) -> Txn:
    return Txn(
        id=tid,
        account_id=account,
        transaction_date=day,
        amount=Decimal(amount),
        direction=direction,
        counterparty_name=counterparty,
    )


def _by_source(candidates: list[RelationCandidate]) -> dict[str, RelationCandidate]:
    return {c.source_transaction_id: c for c in candidates}


def test_full_refund_is_reversal() -> None:
    debit = _txn("d1", amount="100.00", day=date(2026, 9, 1))
    credit = _txn("c1", amount="100.00", day=date(2026, 9, 2), direction="CREDIT")
    result = detect_refund_relations([debit, credit])
    assert len(result) == 1
    assert result[0].source_transaction_id == "d1"
    assert result[0].target_transaction_id == "c1"
    assert result[0].relation_type == RelationType.REVERSAL.value


def test_partial_refund_is_refund() -> None:
    debit = _txn("d1", amount="100.00")
    credit = _txn("c1", amount="40.00", direction="CREDIT", day=date(2026, 9, 10))
    result = detect_refund_relations([debit, credit])
    assert len(result) == 1
    assert result[0].relation_type == RelationType.REFUND.value


def test_different_counterparty_no_relation() -> None:
    debit = _txn("d1", counterparty="商户A")
    credit = _txn("c1", direction="CREDIT", counterparty="商户B")
    assert detect_refund_relations([debit, credit]) == []


def test_different_account_no_relation() -> None:
    debit = _txn("d1", account="a")
    credit = _txn("c1", account="b", direction="CREDIT")
    assert detect_refund_relations([debit, credit]) == []


def test_credit_before_debit_no_relation() -> None:
    debit = _txn("d1", day=date(2026, 9, 5))
    credit = _txn("c1", day=date(2026, 9, 1), direction="CREDIT")
    assert detect_refund_relations([debit, credit]) == []


def test_credit_exceeding_debit_no_relation() -> None:
    debit = _txn("d1", amount="100.00")
    credit = _txn("c1", amount="150.00", direction="CREDIT")
    assert detect_refund_relations([debit, credit]) == []


def test_greedy_single_matching() -> None:
    # Two refunds against the same debit: only the first (earliest) binds.
    debit = _txn("d1", amount="100.00", day=date(2026, 9, 1))
    first = _txn("c1", amount="30.00", direction="CREDIT", day=date(2026, 9, 2))
    second = _txn("c2", amount="20.00", direction="CREDIT", day=date(2026, 9, 3))
    result = detect_refund_relations([debit, first, second])
    assert len(result) == 1
    assert result[0].target_transaction_id == "c1"


def test_counterparty_normalized() -> None:
    # Whitespace/case differences must still match.
    debit = _txn("d1", counterparty=" 商户 ")
    credit = _txn("c1", direction="CREDIT", counterparty="商户")
    assert len(detect_refund_relations([debit, credit])) == 1
