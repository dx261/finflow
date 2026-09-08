"""Account balance snapshot API tests."""

from decimal import Decimal

import httpx


async def _create_account(
    client: httpx.AsyncClient, headers: dict[str, str], name: str = "Snap"
) -> dict:
    banks = (await client.get("/api/v1/banks", headers=headers)).json()
    response = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "bank_id": banks[0]["id"],
            "name": name,
            "actual_balance": "1000.00",
            "minimum_balance": "200.00",
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_create_and_list_snapshots(
    client: httpx.AsyncClient, seeded_banks, auth_headers
) -> None:
    account = await _create_account(client, auth_headers)

    created = await client.post(
        f"/api/v1/accounts/{account['id']}/balances", headers=auth_headers, json={}
    )
    assert created.status_code == 201
    body = created.json()
    # Snapshot records the account's current balances (actual + planning).
    assert Decimal(body["balance"]) == Decimal("1000")
    assert Decimal(body["available_balance"]) == Decimal("800")
    assert body["source"] == "MANUAL"

    listed = (
        await client.get(f"/api/v1/accounts/{account['id']}/balances", headers=auth_headers)
    ).json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]


async def test_snapshot_with_custom_date_and_source(
    client: httpx.AsyncClient, seeded_banks, auth_headers
) -> None:
    account = await _create_account(client, auth_headers)
    response = await client.post(
        f"/api/v1/accounts/{account['id']}/balances",
        headers=auth_headers,
        json={"snapshot_date": "2026-09-01", "source": "STATEMENT"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["snapshot_date"] == "2026-09-01"
    assert body["source"] == "STATEMENT"


async def test_snapshots_require_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/accounts/00000000-0000-0000-0000-000000000000/balances")
    assert response.status_code == 401


async def test_snapshot_on_missing_account_404(
    client: httpx.AsyncClient, seeded_banks, auth_headers
) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    response = await client.post(
        f"/api/v1/accounts/{missing}/balances", headers=auth_headers, json={}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
