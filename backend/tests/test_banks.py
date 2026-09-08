"""Bank catalog API tests."""


def test_list_default_banks(client, seeded_banks, auth_headers) -> None:
    response = client.get("/api/v1/banks", headers=auth_headers)
    assert response.status_code == 200
    banks = response.json()
    assert len(banks) == 7
    codes = {bank["code"] for bank in banks}
    assert {"ICBC", "CMB", "CCB", "GENERIC"} <= codes


def test_banks_require_authentication(client) -> None:
    response = client.get("/api/v1/banks")
    assert response.status_code == 401


def test_owner_can_create_bank(client, db_reset, auth_headers) -> None:
    response = client.post(
        "/api/v1/banks",
        headers=auth_headers,
        json={"code": "TEST", "name": "测试银行", "country": "CN"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "TEST"
    assert body["statement_parser_type"] == "GENERIC"


def test_duplicate_bank_code_conflicts(client, seeded_banks, auth_headers) -> None:
    response = client.post(
        "/api/v1/banks", headers=auth_headers, json={"code": "ICBC", "name": "重复"}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_viewer_cannot_create_bank(client, db_reset) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"username": "owner", "email": "o@test.dev", "password": "password123"},
    )
    client.post(
        "/api/v1/auth/register",
        json={"username": "viewer", "email": "v@test.dev", "password": "password123"},
    )
    login = client.post("/api/v1/auth/login", json={"login": "viewer", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post("/api/v1/banks", headers=headers, json={"code": "T2", "name": "无权"})
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_get_and_delete_bank(client, seeded_banks, auth_headers) -> None:
    banks = client.get("/api/v1/banks", headers=auth_headers).json()
    bank_id = next(bank["id"] for bank in banks if bank["code"] == "CMB")

    detail = client.get(f"/api/v1/banks/{bank_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["code"] == "CMB"

    deleted = client.delete(f"/api/v1/banks/{bank_id}", headers=auth_headers)
    assert deleted.status_code == 204

    missing = client.get(f"/api/v1/banks/{bank_id}", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["code"] == "NOT_FOUND"
