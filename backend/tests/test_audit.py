"""Audit log API tests."""

from decimal import Decimal

import httpx


async def _create_account(
    client: httpx.AsyncClient, headers: dict[str, str], name: str = "Audit"
) -> dict:
    banks = (await client.get("/api/v1/banks", headers=headers)).json()
    response = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "bank_id": banks[0]["id"],
            "name": name,
            "actual_balance": "1000.00",
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_audit_requires_owner(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/audit")
    assert response.status_code == 401


async def test_viewer_cannot_read_audit(client: httpx.AsyncClient, db_reset) -> None:
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
    response = await client.get("/api/v1/audit", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


async def test_account_create_and_update_are_audited(
    client: httpx.AsyncClient, seeded_banks, auth_headers
) -> None:
    account = await _create_account(client, auth_headers)

    await client.put(
        f"/api/v1/accounts/{account['id']}",
        headers=auth_headers,
        json={"minimum_balance": "50.00"},
    )

    logs = (await client.get("/api/v1/audit", headers=auth_headers)).json()
    actions = [log["action"] for log in logs]
    assert "ACCOUNT_CREATED" in actions
    assert "ACCOUNT_UPDATED" in actions

    updated = next(log for log in logs if log["action"] == "ACCOUNT_UPDATED")
    assert updated["resource_type"] == "account"
    assert updated["resource_id"] == account["id"]
    assert Decimal(updated["before_data"]["minimum_balance"]) == Decimal("0")
    assert Decimal(updated["after_data"]["minimum_balance"]) == Decimal("50")
    assert updated["trace_id"]


async def test_audit_filters(client: httpx.AsyncClient, seeded_banks, auth_headers) -> None:
    account = await _create_account(client, auth_headers)

    by_action = (
        await client.get(
            "/api/v1/audit", headers=auth_headers, params={"action": "ACCOUNT_CREATED"}
        )
    ).json()
    assert all(log["action"] == "ACCOUNT_CREATED" for log in by_action)

    by_resource = (
        await client.get(
            "/api/v1/audit",
            headers=auth_headers,
            params={"resource_type": "account", "resource_id": account["id"]},
        )
    ).json()
    assert all(log["resource_id"] == account["id"] for log in by_resource)
