"""Anonymous showcase access and reversible authentication boundaries."""

import pytest
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.modules.auth.demo import DEMO_USER_ID
from app.modules.auth.models import User, UserStatus


@pytest.fixture
def demo_mode(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)


async def test_public_config_and_stable_demo_identity(client, db_reset, demo_mode):
    config = await client.get("/api/v1/auth/config")
    assert config.json() == {"demo_mode": True, "local_demo": False}
    first = await client.get("/api/v1/auth/me")
    second = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer stale"})
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"] == str(DEMO_USER_ID)
    assert first.json()["role"] == "OWNER"
    assert "password_hash" not in first.json()


@pytest.mark.parametrize(
    ("endpoint", "payload"),
    [
        ("register", {"username": "new", "email": "new@example.com", "password": "password123"}),
        ("login", {"login": "owner", "password": "password123"}),
        ("refresh", {"refresh_token": "old-token"}),
    ],
)
async def test_demo_disables_auth_endpoints(client, db_reset, demo_mode, endpoint, payload):
    response = await client.post(f"/api/v1/auth/{endpoint}", json=payload)
    assert response.status_code == 403


async def test_demo_isolated_and_restoring_auth_preserves_real_data(
    client, seeded_banks, monkeypatch
):
    registered = await client.post(
        "/api/v1/auth/register",
        json={"username": "real", "email": "real@example.com", "password": "password123"},
    )
    real_id = registered.json()["id"]
    tokens = await client.post(
        "/api/v1/auth/login", json={"login": "real", "password": "password123"}
    )
    headers = {"Authorization": f"Bearer {tokens.json()['access_token']}"}
    banks = await client.get("/api/v1/banks", headers=headers)
    payload = {"bank_id": banks.json()[0]["id"], "name": "Private", "currency": "CNY"}
    private = await client.post("/api/v1/accounts", json=payload, headers=headers)
    assert private.status_code == 201

    monkeypatch.setattr(settings, "demo_mode", True)
    assert (await client.get("/api/v1/accounts", headers=headers)).json() == []
    demo = await client.post("/api/v1/accounts", json={**payload, "name": "Demo"})
    assert demo.status_code == 201
    visible = (await client.get("/api/v1/accounts")).json()
    assert [a["name"] for a in visible] == ["Demo"]
    assert (await client.get(f"/api/v1/accounts/{private.json()['id']}")).status_code == 403

    monkeypatch.setattr(settings, "demo_mode", False)
    assert (await client.get("/api/v1/auth/config")).json() == {
        "demo_mode": False,
        "local_demo": False,
    }
    assert (await client.get("/api/v1/accounts")).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=headers)).json()["id"] == real_id
    assert [a["name"] for a in (await client.get("/api/v1/accounts", headers=headers)).json()] == [
        "Private"
    ]
    demo_headers = {"Authorization": f"Bearer {create_access_token(DEMO_USER_ID)}"}
    assert (await client.get("/api/v1/auth/me", headers=demo_headers)).status_code == 401


async def test_first_real_registration_after_demo_remains_owner(client, db_reset, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)
    await client.get("/api/v1/auth/me")
    monkeypatch.setattr(settings, "demo_mode", False)
    registered = await client.post(
        "/api/v1/auth/register",
        json={"username": "real", "email": "real@example.com", "password": "password123"},
    )
    assert registered.status_code == 201
    assert registered.json()["role"] == "OWNER"


async def test_disabled_demo_user_is_not_reactivated(client, db_reset, demo_mode):
    await client.get("/api/v1/auth/me")
    async with AsyncSessionLocal() as session:
        user = await session.get(User, DEMO_USER_ID)
        user.status = UserStatus.DISABLED
        await session.commit()
    assert (await client.get("/api/v1/auth/me")).status_code == 403
