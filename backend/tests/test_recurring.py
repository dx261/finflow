"""Recurring payment tests: due-date logic and API."""

import uuid
from datetime import date
from decimal import Decimal

from app.modules.payments.models import PaymentPriority
from app.modules.recurring.models import RecurringFrequency, RecurringPayment
from app.modules.recurring.service import next_due_dates


def _rec(**overrides) -> RecurringPayment:
    defaults: dict = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "name": "房租",
        "amount": Decimal("8000.00"),
        "currency": "CNY",
        "frequency": RecurringFrequency.MONTHLY,
        "day_of_month": 1,
        "start_date": date(2026, 1, 1),
        "end_date": None,
        "preferred_account_id": None,
        "priority": PaymentPriority.NORMAL,
        "enabled": True,
    }
    defaults.update(overrides)
    return RecurringPayment(**defaults)


# --- next_due_dates unit tests -------------------------------------------


def test_monthly_due_dates() -> None:
    dates = next_due_dates(_rec(), date(2026, 1, 1), date(2026, 3, 31))
    assert dates == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_day_31_clamped_to_month_end() -> None:
    rec = _rec(day_of_month=31)
    dates = next_due_dates(rec, date(2026, 4, 1), date(2026, 6, 30))
    assert dates == [date(2026, 4, 30), date(2026, 5, 31), date(2026, 6, 30)]


def test_quarterly_due_dates() -> None:
    rec = _rec(frequency=RecurringFrequency.QUARTERLY, day_of_month=10)
    dates = next_due_dates(rec, date(2026, 1, 1), date(2026, 12, 31))
    assert dates == [date(2026, 1, 10), date(2026, 4, 10), date(2026, 7, 10), date(2026, 10, 10)]


def test_yearly_due_dates() -> None:
    rec = _rec(frequency=RecurringFrequency.YEARLY, day_of_month=15)
    dates = next_due_dates(rec, date(2026, 1, 1), date(2028, 12, 31))
    assert dates == [date(2026, 1, 15), date(2027, 1, 15), date(2028, 1, 15)]


def test_weekly_due_dates() -> None:
    rec = _rec(frequency=RecurringFrequency.WEEKLY, start_date=date(2026, 1, 5))
    dates = next_due_dates(rec, date(2026, 1, 5), date(2026, 1, 20))
    assert dates == [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19)]


def test_disabled_returns_nothing() -> None:
    assert next_due_dates(_rec(enabled=False), date(2026, 1, 1), date(2026, 12, 31)) == []


def test_end_date_respected() -> None:
    rec = _rec(end_date=date(2026, 2, 28))
    dates = next_due_dates(rec, date(2026, 1, 1), date(2026, 3, 31))
    assert dates == [date(2026, 1, 1), date(2026, 2, 1)]


def test_window_filters_dates() -> None:
    dates = next_due_dates(_rec(), date(2026, 2, 1), date(2026, 2, 28))
    assert dates == [date(2026, 2, 1)]


# --- API tests -------------------------------------------------------------


async def _create_monthly_rent(client, auth_headers) -> None:
    response = await client.post(
        "/api/v1/recurring",
        headers=auth_headers,
        json={
            "name": "房租",
            "amount": "8000.00",
            "frequency": "MONTHLY",
            "day_of_month": 1,
            "start_date": "2026-09-01",
        },
    )
    assert response.status_code == 201, response.text


async def test_create_and_list_recurring(client, seeded_banks, auth_headers) -> None:
    await _create_monthly_rent(client, auth_headers)

    listed = await client.get("/api/v1/recurring", headers=auth_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["frequency"] == "MONTHLY"
    assert body[0]["enabled"] is True


async def test_generate_is_idempotent(client, seeded_banks, auth_headers) -> None:
    await _create_monthly_rent(client, auth_headers)
    params = {"from_date": "2026-09-01", "to_date": "2026-12-31"}

    first = await client.post("/api/v1/recurring/generate", headers=auth_headers, params=params)
    assert first.status_code == 200
    assert first.json()["created"] == 4  # Sep/Oct/Nov/Dec

    second = await client.post("/api/v1/recurring/generate", headers=auth_headers, params=params)
    assert second.status_code == 200
    assert second.json()["created"] == 0  # idempotent — no duplicates


async def test_generated_plans_appear_as_planned(client, seeded_banks, auth_headers) -> None:
    await _create_monthly_rent(client, auth_headers)
    params = {"from_date": "2026-09-01", "to_date": "2026-12-31"}
    await client.post("/api/v1/recurring/generate", headers=auth_headers, params=params)

    payments = await client.get(
        "/api/v1/payments", headers=auth_headers, params={"status": "PLANNED"}
    )
    body = payments.json()
    assert len(body) == 4
    assert all(p["status"] == "PLANNED" for p in body)
    assert {p["planned_date"] for p in body} == {
        "2026-09-01",
        "2026-10-01",
        "2026-11-01",
        "2026-12-01",
    }


async def test_viewer_cannot_create_recurring(client, seeded_banks) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"username": "owner", "email": "o@test.dev", "password": "password123"},
    )
    await client.post(
        "/api/v1/auth/register",
        json={"username": "viewer", "email": "v@test.dev", "password": "password123"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"login": "viewer", "password": "password123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.post(
        "/api/v1/recurring",
        headers=headers,
        json={
            "name": "无权",
            "amount": "100",
            "frequency": "MONTHLY",
            "day_of_month": 1,
            "start_date": "2026-09-01",
        },
    )
    assert response.status_code == 403
