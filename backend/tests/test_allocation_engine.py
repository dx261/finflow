"""Allocation engine tests (CODING_PLAN.md §37, §94)."""

from datetime import date
from decimal import Decimal

from app.modules.allocation.engine import (
    AccountInput,
    AllocationResult,
    PaymentInput,
    Priority,
    allocate,
)


def _payment(
    pid: str,
    amount: str,
    *,
    priority: Priority = Priority.NORMAL,
    planned: date = date(2026, 10, 1),
    preferred: str | None = None,
) -> PaymentInput:
    return PaymentInput(
        id=pid,
        amount=Decimal(amount),
        currency="CNY",
        planned_date=planned,
        priority=priority,
        preferred_account_id=preferred,
    )


def _account(
    aid: str, available: str, *, include: bool = True, priority: Priority = Priority.NORMAL
) -> AccountInput:
    return AccountInput(
        id=aid,
        currency="CNY",
        planning_available=Decimal(available),
        include_in_allocation=include,
        priority=priority,
    )


def _allocations(result: AllocationResult) -> dict[str, Decimal]:
    return dict(result.allocations)


def test_exact_allocation() -> None:
    result = allocate([_payment("p1", "100")], [_account("a1", "100")])[0]
    assert _allocations(result) == {"a1": Decimal("100.00")}
    assert result.shortage == Decimal("0")


def test_split_across_accounts() -> None:
    # A 50, B 50, payment 80 -> 50 + 30.
    result = allocate([_payment("p1", "80")], [_account("a", "50"), _account("b", "50")])[0]
    assert _allocations(result) == {"a": Decimal("50.00"), "b": Decimal("30.00")}


def test_minimum_reserve_produces_shortage() -> None:
    # Balance 100, minimum 40 -> available 60; payment 80 -> shortage 20.
    result = allocate([_payment("p1", "80")], [_account("a", "60")])[0]
    assert _allocations(result) == {"a": Decimal("60.00")}
    assert result.shortage == Decimal("20.00")


def test_reserved_funds_reduce_available() -> None:
    # Balance 100, reserved 30, minimum 20 -> planning available 50.
    result = allocate([_payment("p1", "50")], [_account("a", "50")])[0]
    assert _allocations(result) == {"a": Decimal("50.00")}
    assert result.shortage == Decimal("0")


def test_plan_example_drains_smaller_available_first() -> None:
    # CMB available 7000, ICBC available 12000, rent 10000 -> CMB 7000 + ICBC 3000.
    cmb = AccountInput(id="cmb", currency="CNY", planning_available=Decimal("7000"))
    icbc = AccountInput(id="icbc", currency="CNY", planning_available=Decimal("12000"))
    result = allocate([_payment("rent", "10000")], [cmb, icbc])[0]
    assert _allocations(result) == {"cmb": Decimal("7000.00"), "icbc": Decimal("3000.00")}


def test_preferred_account_used_first() -> None:
    # Both have 5000; preferred (b) should be drained first even though
    # ascending-available order would pick a.
    result = allocate(
        [_payment("p1", "8000", preferred="b")],
        [_account("a", "5000"), _account("b", "5000")],
    )[0]
    assert _allocations(result) == {"b": Decimal("5000.00"), "a": Decimal("3000.00")}


def test_currency_mismatch_excluded() -> None:
    payment = PaymentInput(
        id="p1", amount=Decimal("100"), currency="CNY", planned_date=date(2026, 10, 1)
    )
    usd_account = AccountInput(id="usd", currency="USD", planning_available=Decimal("100"))
    result = allocate([payment], [usd_account])[0]
    assert result.allocations == []
    assert result.shortage == Decimal("100.00")


def test_excluded_account_skipped() -> None:
    result = allocate(
        [_payment("p1", "100")],
        [_account("disabled", "100", include=False), _account("ok", "100")],
    )[0]
    assert _allocations(result) == {"ok": Decimal("100.00")}


def test_payment_priority_order() -> None:
    rent = _payment("rent", "50", priority=Priority.LOW, planned=date(2026, 10, 1))
    tuition = _payment("tuition", "50", priority=Priority.URGENT, planned=date(2026, 11, 1))
    account = _account("a", "80")

    results = {r.payment_id: r for r in allocate([rent, tuition], [account])}
    # Urgent tuition is funded first; rent gets the remainder.
    assert _allocations(results["tuition"]) == {"a": Decimal("50.00")}
    assert _allocations(results["rent"]) == {"a": Decimal("30.00")}
    assert results["rent"].shortage == Decimal("20.00")


def test_higher_priority_drains_more() -> None:
    # Tuition (urgent) takes the available 100; rent gets nothing.
    rent = _payment("rent", "100", priority=Priority.LOW)
    tuition = _payment("tuition", "100", priority=Priority.URGENT)
    results = {r.payment_id: r for r in allocate([rent, tuition], [_account("a", "100")])}
    assert _allocations(results["tuition"]) == {"a": Decimal("100.00")}
    assert results["rent"].shortage == Decimal("100.00")
