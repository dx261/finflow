"""Bank catalog API tests."""

import httpx


async def test_list_default_banks(client: httpx.AsyncClient, seeded_banks, auth_headers) -> None:
    response = await client.get("/api/v1/banks", headers=auth_headers)
    assert response.status_code == 200
    banks = response.json()
    assert len(banks) == 7
    codes = {bank["code"] for bank in banks}
    assert {"ICBC", "CMB", "CCB", "GENERIC"} <= codes


async def test_banks_require_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/banks")
    assert response.status_code == 401


async def test_owner_can_create_bank(client: httpx.AsyncClient, db_reset, auth_headers) -> None:
    response = await client.post(
        "/api/v1/banks",
        headers=auth_headers,
        json={"code": "TEST", "name": "测试银行", "country": "CN"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "TEST"
    assert body["statement_parser_type"] == "GENERIC"


async def test_duplicate_bank_code_conflicts(
    client: httpx.AsyncClient, seeded_banks, auth_headers
) -> None:
    response = await client.post(
        "/api/v1/banks", headers=auth_headers, json={"code": "ICBC", "name": "重复"}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


async def test_viewer_cannot_create_bank(client: httpx.AsyncClient, db_reset) -> None:
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
        "/api/v1/banks", headers=headers, json={"code": "T2", "name": "无权"}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


async def test_get_and_delete_bank(client: httpx.AsyncClient, seeded_banks, auth_headers) -> None:
    banks = (await client.get("/api/v1/banks", headers=auth_headers)).json()
    bank_id = next(bank["id"] for bank in banks if bank["code"] == "CMB")

    detail = await client.get(f"/api/v1/banks/{bank_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["code"] == "CMB"

    deleted = await client.delete(f"/api/v1/banks/{bank_id}", headers=auth_headers)
    assert deleted.status_code == 204

    missing = await client.get(f"/api/v1/banks/{bank_id}", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["code"] == "NOT_FOUND"
