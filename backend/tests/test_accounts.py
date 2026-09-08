"""Account API tests: CRUD and the three planning-balance concepts."""

import uuid
from decimal import Decimal

import httpx


async def _first_bank_id(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    banks = (await client.get("/api/v1/banks", headers=headers)).json()
    return banks[0]["id"]


async def test_create_account_with_planning_balances(
    client: httpx.AsyncClient, seeded_banks, auth_headers
) -> None:
    bank_id = await _first_bank_id(client, auth_headers)
    response = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "bank_id": bank_id,
            "name": "ICBC 储蓄",
            "actual_balance": "100.00",
            "minimum_balance": "40.00",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "ICBC 储蓄"
    assert body["currency"] == "CNY"
    assert body["account_type"] == "CHECKING"
    # planning_available = 100 - 0 (reserved) - 40 (minimum) = 60
    assert Decimal(body["reserved_amount"]) == Decimal("0")
    assert Decimal(body["planning_available"]) == Decimal("60")


async def test_accounts_require_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/accounts")
    assert response.status_code == 401


async def test_list_accounts(client: httpx.AsyncClient, seeded_banks, auth_headers) -> None:
    bank_id = await _first_bank_id(client, auth_headers)
    await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={"bank_id": bank_id, "name": "A", "actual_balance": "1000.00"},
    )
    await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={"bank_id": bank_id, "name": "B", "actual_balance": "500.00"},
    )
    accounts = (await client.get("/api/v1/accounts", headers=auth_headers)).json()
    assert len(accounts) == 2
    assert {account["name"] for account in accounts} == {"A", "B"}


async def test_update_account_recomputes_planning_available(
    client: httpx.AsyncClient, seeded_banks, auth_headers
) -> None:
    bank_id = await _first_bank_id(client, auth_headers)
    created = (
        await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={"bank_id": bank_id, "name": "Saving", "actual_balance": "100.00"},
        )
    ).json()

    updated = await client.put(
        f"/api/v1/accounts/{created['id']}",
        headers=auth_headers,
        json={"minimum_balance": "20.00"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert Decimal(body["minimum_balance"]) == Decimal("20")
    assert Decimal(body["planning_available"]) == Decimal("80")


async def test_viewer_cannot_create_account(client: httpx.AsyncClient, db_reset) -> None:
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
        "/api/v1/accounts", headers=headers, json={"bank_id": str(uuid.uuid4()), "name": "X"}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


async def test_delete_account(client: httpx.AsyncClient, seeded_banks, auth_headers) -> None:
    bank_id = await _first_bank_id(client, auth_headers)
    created = (
        await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={"bank_id": bank_id, "name": "Temp"},
        )
    ).json()

    deleted = await client.delete(f"/api/v1/accounts/{created['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    missing = await client.get(f"/api/v1/accounts/{created['id']}", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["code"] == "NOT_FOUND"
