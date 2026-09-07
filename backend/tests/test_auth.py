"""Authentication tests: hashing, JWT, register/login/refresh/me."""

import uuid

import pytest
from app.core.database import Base, engine
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
async def _clean_tables() -> None:
    """Reset the schema before each test so users do not accumulate."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


# --- security unit tests -------------------------------------------------


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_password_hash_is_salted() -> None:
    assert hash_password("same-password") != hash_password("same-password")


def test_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"


def test_refresh_token_cannot_be_used_as_access() -> None:
    token = create_refresh_token(uuid.uuid4())
    assert decode_token(token, expected_type="refresh")["type"] == "refresh"
    with pytest.raises(AuthenticationError):
        decode_token(token)  # defaults to expected_type="access"


# --- API flow tests ------------------------------------------------------


def _register(username: str, email: str, password: str = "password123") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert response.status_code == 201
    return response.json()


def test_first_registered_user_becomes_owner() -> None:
    body = _register("owner1", "owner1@example.com")
    assert body["role"] == "OWNER"
    assert body["status"] == "ACTIVE"
    assert "id" in body


def test_second_user_is_viewer() -> None:
    _register("first", "first@example.com")
    body = _register("second", "second@example.com")
    assert body["role"] == "VIEWER"


def test_duplicate_username_conflicts() -> None:
    _register("dup", "dup@example.com")
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "dup", "email": "other@example.com", "password": "password123"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_duplicate_email_conflicts() -> None:
    _register("email1", "shared@example.com")
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "email2", "email": "shared@example.com", "password": "password123"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_login_and_me_flow() -> None:
    _register("flow", "flow@example.com")
    login = client.post(
        "/api/v1/auth/login",
        json={"login": "flow", "password": "password123"},
    )
    assert login.status_code == 200
    tokens = login.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "flow"


def test_login_via_email() -> None:
    _register("maillogin", "maillogin@example.com")
    login = client.post(
        "/api/v1/auth/login",
        json={"login": "maillogin@example.com", "password": "password123"},
    )
    assert login.status_code == 200


def test_login_wrong_password_rejected() -> None:
    _register("badpass", "badpass@example.com")
    response = client.post(
        "/api/v1/auth/login",
        json={"login": "badpass", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_me_requires_authentication() -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


def test_refresh_flow() -> None:
    _register("refresh", "refresh@example.com")
    login = client.post(
        "/api/v1/auth/login",
        json={"login": "refresh", "password": "password123"},
    )
    refresh_token = login.json()["refresh_token"]

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_invalid_refresh_token_rejected() -> None:
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"
