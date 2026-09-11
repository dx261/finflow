"""Constraint-aware greedy allocation engine.

Pure function: given payments and accounts, produce a recommended funding
plan. Constraints respected:

- currency must match
- only accounts with planning_available > 0 are used
- minimum balance is already reflected in planning_available
- accounts excluded from allocation (include_in_allocation=False) are skipped
- preferred account is used first

Payments are funded in priority order; each account is drained in
ascending available order so larger reserves are preserved (the greedy
strategy from CODING_PLAN.md §34-37).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from functools import partial


class Priority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


_PRIORITY_RANK = {
    Priority.URGENT: 4,
    Priority.HIGH: 3,
    Priority.NORMAL: 2,
    Priority.LOW: 1,
}


@dataclass(frozen=True)
class AccountInput:
    id: str
    currency: str
    planning_available: Decimal
    include_in_allocation: bool = True
    priority: Priority = Priority.NORMAL


@dataclass(frozen=True)
class PaymentInput:
    id: str
    amount: Decimal
    currency: str
    planned_date: date
    priority: Priority = Priority.NORMAL
    preferred_account_id: str | None = None


@dataclass
class AllocationResult:
    payment_id: str
    allocations: list[tuple[str, Decimal]] = field(default_factory=list)
    shortage: Decimal = Decimal("0")


def _account_sort_key(
    account: AccountInput,
    *,
    available: dict[str, Decimal],
    preferred_id: str | None,
) -> tuple[int, Decimal, int, str]:
    """Sort accounts: preferred first, then ascending available, then
    account priority (higher first), then id for stability."""
    is_preferred = account.id == preferred_id
    return (
        0 if is_preferred else 1,
        available[account.id],
        -_PRIORITY_RANK[account.priority],
        account.id,
    )


def allocate(payments: list[PaymentInput], accounts: list[AccountInput]) -> list[AllocationResult]:
    """Return the recommended funding plan (amounts only, no persistence)."""
    available = {account.id: account.planning_available for account in accounts}
    results: list[AllocationResult] = []

    ordered_payments = sorted(
        payments,
        key=lambda p: (
            -_PRIORITY_RANK[p.priority],
            p.planned_date,
            p.amount,
            p.id,
        ),
    )

    for payment in ordered_payments:
        remaining = payment.amount
        result = AllocationResult(payment_id=payment.id)
        sort_key = partial(
            _account_sort_key,
            available=available,
            preferred_id=payment.preferred_account_id,
        )

        eligible = [
            account
            for account in accounts
            if account.currency == payment.currency
            and account.include_in_allocation
            and available[account.id] > 0
        ]

        for account in sorted(eligible, key=sort_key):
            if remaining <= 0:
                break
            take = min(remaining, available[account.id])
            if take > 0:
                result.allocations.append((account.id, take))
                available[account.id] -= take
                remaining -= take

        result.shortage = remaining
        results.append(result)

    return results
