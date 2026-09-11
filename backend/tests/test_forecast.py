"""Forecast engine and API tests."""

from datetime import date
from decimal import Decimal

from app.modules.forecast.engine import (
    ForecastAccount,
    ForecastFlow,
    collect_warnings,
    forecast_account,
)


def _account(balance: str = "50000.00", minimum: str = "10000.00") -> ForecastAccount:
    return ForecastAccount(
        id="acc", actual_balance=Decimal(balance), minimum_balance=Decimal(minimum), currency="CNY"
    )


def _flow(day: int, amount: str, kind: str, account: str = "acc") -> ForecastFlow:
    return ForecastFlow(date(2026, 10, day), Decimal(amount), account, kind)


def test_income_and_expense_affect_balance() -> None:
    flows = [
        _flow(5, "8000.00", "expense"),
        _flow(15, "15000.00", "income"),
    ]
    days = forecast_account(_account(), flows, horizon_days=20, start=date(2026, 10, 1))
    assert days[0].starting_balance == Decimal("50000.00")
    # Day 5 (index 4): -8000
    assert days[4].expected_expense == Decimal("8000.00")
    assert days[4].ending_balance == Decimal("42000.00")
    # Day 15 (index 14): +15000
    assert days[14].expected_income == Decimal("15000.00")
    assert days[14].ending_balance == Decimal("57000.00")
    # Last day carries forward.
    assert days[19].ending_balance == Decimal("57000.00")


def test_below_minimum_warning() -> None:
    flows = [_flow(1, "45000.00", "expense")]
    days = forecast_account(_account(), flows, horizon_days=5, start=date(2026, 10, 1))
    warnings = collect_warnings(days)
    # 50000 - 45000 = 5000 < 10000 minimum, for every remaining day.
    assert len(warnings) == 5
    assert all(day.below_minimum for day in warnings)
    assert days[0].ending_balance == Decimal("5000.00")


def test_flow_outside_horizon_ignored() -> None:
    # Oct 31 is outside the Oct 1-10 horizon.
    flows = [_flow(31, "8000.00", "expense")]
    days = forecast_account(_account(), flows, horizon_days=10, start=date(2026, 10, 1))
    assert days[9].ending_balance == Decimal("50000.00")


def test_other_account_flow_ignored() -> None:
    flows = [_flow(1, "8000.00", "expense", account="other")]
    days = forecast_account(_account(), flows, horizon_days=5, start=date(2026, 10, 1))
    assert days[4].ending_balance == Decimal("50000.00")


# --- API tests -------------------------------------------------------------


async def _create_reserved_payment(client, auth_headers, account_id, amount="8000.00") -> str:
    payment = await client.post(
        "/api/v1/payments",
        headers=auth_headers,
        json={"name": "房租", "amount": amount, "planned_date": "2026-12-01"},
    )
    payment_id = payment.json()["id"]
    await client.post(
        f"/api/v1/payments/{payment_id}/transition",
        headers=auth_headers,
        json={"target_status": "PLANNED"},
    )
    await client.post(f"/api/v1/payments/{payment_id}/allocations/preview", headers=auth_headers)
    await client.post(f"/api/v1/payments/{payment_id}/allocations/confirm", headers=auth_headers)
    return payment_id


async def test_forecast_endpoint(client, seeded_banks, auth_headers) -> None:
    banks = (await client.get("/api/v1/banks", headers=auth_headers)).json()
    bank_id = next(bank["id"] for bank in banks if bank["code"] == "ICBC")
    account = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={"bank_id": bank_id, "name": "账户", "actual_balance": "50000"},
    )
    account_id = account.json()["id"]

    # Scheduled income in the future.
    await client.post(
        "/api/v1/cashflow-plans",
        headers=auth_headers,
        json={
            "type": "INCOME",
            "name": "工资",
            "amount": "15000.00",
            "date": "2026-12-15",
            "account_id": account_id,
        },
    )
    await _create_reserved_payment(client, auth_headers, account_id)

    response = await client.get("/api/v1/forecast", headers=auth_headers, params={"days": 30})
    assert response.status_code == 200, response.text
    body = response.json()
    assert account_id in body["accounts"]
    assert len(body["aggregate"]) == 30
    assert len(body["accounts"][account_id]) == 30


async def test_cashflow_plan_crud(client, seeded_banks, auth_headers) -> None:
    created = await client.post(
        "/api/v1/cashflow-plans",
        headers=auth_headers,
        json={"type": "EXPENSE", "name": "保险", "amount": "3000.00", "date": "2027-01-01"},
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["id"]

    listed = await client.get("/api/v1/cashflow-plans", headers=auth_headers)
    assert len(listed.json()) == 1

    updated = await client.put(
        f"/api/v1/cashflow-plans/{plan_id}",
        headers=auth_headers,
        json={"amount": "3500.00", "status": "COMPLETED"},
    )
    assert updated.json()["amount"] == "3500.00"
    assert updated.json()["status"] == "COMPLETED"

    deleted = await client.delete(f"/api/v1/cashflow-plans/{plan_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/cashflow-plans", headers=auth_headers)).json() == []
