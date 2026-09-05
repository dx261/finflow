"""Health endpoint tests for the FinFlow API."""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # Dependency fields exist and are honest about their current state.
    assert body["database"] == "not_configured"
    assert body["redis"] == "not_configured"


def test_health_exposes_api_prefix() -> None:
    # The endpoint must live under the versioned API prefix.
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_openapi_docs_available() -> None:
    response = client.get("/docs")
    assert response.status_code == 200
