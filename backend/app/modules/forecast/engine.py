"""Cash flow forecast engine (§53-56).

Pure functions: given account balances, upcoming payments and scheduled
income, produce a daily balance projection per account. Warnings flag days
where the projected balance falls below the account's minimum reserve.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class ForecastAccount:
    id: str
    actual_balance: Decimal
    minimum_balance: Decimal
    currency: str


@dataclass(frozen=True)
class ForecastFlow:
    date: date
    amount: Decimal
    account_id: str
    kind: str  # "income" | "expense"


@dataclass(frozen=True)
class ForecastDay:
    date: date
    starting_balance: Decimal
    expected_income: Decimal
    expected_expense: Decimal
    ending_balance: Decimal
    below_minimum: bool


def forecast_account(
    account: ForecastAccount,
    flows: list[ForecastFlow],
    horizon_days: int,
    start: date | None = None,
) -> list[ForecastDay]:
    """Project one account's balance day by day over the horizon."""
    start = start or date.today()
    end = start + timedelta(days=horizon_days)

    flows_by_day: dict[date, tuple[Decimal, Decimal]] = {}
    for flow in flows:
        if flow.account_id != account.id or flow.date < start or flow.date > end:
            continue
        income, expense = flows_by_day.get(flow.date, (Decimal("0"), Decimal("0")))
        if flow.kind == "income":
            income += flow.amount
        else:
            expense += flow.amount
        flows_by_day[flow.date] = (income, expense)

    days: list[ForecastDay] = []
    balance = account.actual_balance
    for offset in range(horizon_days):
        day = start + timedelta(days=offset)
        income, expense = flows_by_day.get(day, (Decimal("0"), Decimal("0")))
        ending = balance + income - expense
        days.append(
            ForecastDay(
                date=day,
                starting_balance=balance,
                expected_income=income,
                expected_expense=expense,
                ending_balance=ending,
                below_minimum=ending < account.minimum_balance,
            )
        )
        balance = ending
    return days


def collect_warnings(days: list[ForecastDay]) -> list[ForecastDay]:
    """Return the days whose projected balance is below minimum."""
    return [day for day in days if day.below_minimum]
