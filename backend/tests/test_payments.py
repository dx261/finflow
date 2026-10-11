"""Payment plan CRUD tests."""

import uuid
from decimal import Decimal

from app.core.database import AsyncSessionLocal
from app.modules.payments.models import PaymentPlan, PaymentStatus


async def _create_account(client, auth_headers) -> str:
    banks = (await client.get("/api/v1/banks", headers=auth_headers)).json()
    bank_id = next(bank["id"] for bank in banks if bank["code"] == "ICBC")
    response = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={"bank_id": bank_id, "name": "付款账户", "actual_balance": "10000"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _create_payment(client, auth_headers, **overrides) -> dict:
    payload = {
        "name": "房租",
        "payee_name": "房东",
        "amount": "8000.00",
        "planned_date": "2026-10-01",
        "priority": "HIGH",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/payments", headers=auth_headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_payments_require_auth(client, db_reset) -> None:
    response = await client.get("/api/v1/payments")
    assert response.status_code == 401


async def test_create_payment_defaults_to_draft(client, seeded_banks, auth_headers) -> None:
    payment = await _create_payment(client, auth_headers)
    assert payment["status"] == "DRAFT"
    assert Decimal(payment["amount"]) == Decimal("8000.00")
    assert payment["priority"] == "HIGH"
    assert payment["currency"] == "CNY"


async def test_list_and_get_payment(client, seeded_banks, auth_headers) -> None:
    created = await _create_payment(client, auth_headers)
    payment_id = created["id"]

    listed = await client.get("/api/v1/payments", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    detail = await client.get(f"/api/v1/payments/{payment_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["name"] == "房租"


async def test_list_filter_by_status(client, seeded_banks, auth_headers) -> None:
    await _create_payment(client, auth_headers, name="房租")
    await _create_payment(client, auth_headers, name="学费")

    planned = await client.get(
        "/api/v1/payments", headers=auth_headers, params={"status": "PLANNED"}
    )
    assert planned.json() == []
    draft = await client.get("/api/v1/payments", headers=auth_headers, params={"status": "DRAFT"})
    assert len(draft.json()) == 2


async def test_update_payment(client, seeded_banks, auth_headers) -> None:
    payment = await _create_payment(client, auth_headers)
    payment_id = payment["id"]

    response = await client.put(
        f"/api/v1/payments/{payment_id}",
        headers=auth_headers,
        json={"amount": "9000.00", "priority": "URGENT"},
    )
    assert response.status_code == 200
    assert Decimal(response.json()["amount"]) == Decimal("9000.00")
    assert response.json()["priority"] == "URGENT"


async def test_edit_blocked_outside_draft_or_planned(client, seeded_banks, auth_headers) -> None:
    payment = await _create_payment(client, auth_headers)
    payment_id = payment["id"]
    # Force the payment into a later state directly in the DB.
    async with AsyncSessionLocal() as session:
        record = await session.get(PaymentPlan, uuid.UUID(payment_id))
        record.status = PaymentStatus.RESERVED
        await session.commit()

    response = await client.put(
        f"/api/v1/payments/{payment_id}",
        headers=auth_headers,
        json={"amount": "1000.00"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


async def test_delete_payment(client, seeded_banks, auth_headers) -> None:
    payment = await _create_payment(client, auth_headers)
    response = await client.delete(f"/api/v1/payments/{payment['id']}", headers=auth_headers)
    assert response.status_code == 204

    gone = await client.get(f"/api/v1/payments/{payment['id']}", headers=auth_headers)
    assert gone.status_code == 404


async def test_delete_blocked_outside_draft_or_planned(client, seeded_banks, auth_headers) -> None:
    payment = await _create_payment(client, auth_headers)
    payment_id = payment["id"]
    async with AsyncSessionLocal() as session:
        record = await session.get(PaymentPlan, uuid.UUID(payment_id))
        record.status = PaymentStatus.ALLOCATED
        await session.commit()

    response = await client.delete(f"/api/v1/payments/{payment_id}", headers=auth_headers)
    assert response.status_code == 409


async def test_preferred_account_must_be_owned(client, seeded_banks, auth_headers) -> None:
    response = await client.post(
        "/api/v1/payments",
        headers=auth_headers,
        json={
            "name": "测试",
            "amount": "100",
            "planned_date": "2026-10-01",
            "preferred_account_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


async def test_generic_transition_cannot_bypass_allocation_side_effects(
    client, seeded_banks, auth_headers
) -> None:
    payment = await _create_payment(client, auth_headers)
    payment_id = payment["id"]
    planned = await client.post(
        f"/api/v1/payments/{payment_id}/transition",
        headers=auth_headers,
        json={"target_status": "PLANNED"},
    )
    assert planned.status_code == 200

    bypass = await client.post(
        f"/api/v1/payments/{payment_id}/transition",
        headers=auth_headers,
        json={"target_status": "ALLOCATED"},
    )
    assert bypass.status_code == 409
    detail = await client.get(f"/api/v1/payments/{payment_id}", headers=auth_headers)
    assert detail.json()["status"] == "PLANNED"


async def test_viewer_cannot_create_payment(client, seeded_banks) -> None:
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
        "/api/v1/payments",
        headers=headers,
        json={"name": "无权", "amount": "100", "planned_date": "2026-10-01"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
