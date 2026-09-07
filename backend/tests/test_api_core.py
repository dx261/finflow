"""FastAPI core tests: unified error format and request trace IDs."""

from app.core.exceptions import InsufficientPlanningFundsError
from app.main import app, create_app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_trace_id_passthrough_when_provided() -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "req-123"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"


def test_trace_id_generated_when_missing() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    trace_id = response.headers["X-Request-ID"]
    assert trace_id and len(trace_id) >= 8


def test_not_found_uses_unified_format() -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "NOT_FOUND"
    assert "message" in body
    assert "trace_id" in body


def test_finflow_error_uses_unified_format() -> None:
    app_test = create_app()

    @app_test.get("/funds-test")
    async def funds_test() -> None:
        raise InsufficientPlanningFundsError("Planning funds are insufficient.")

    test_client = TestClient(app_test)
    response = test_client.get("/funds-test")
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "INSUFFICIENT_PLANNING_FUNDS"
    assert body["message"] == "Planning funds are insufficient."
    assert body["trace_id"]


def test_validation_error_uses_unified_format() -> None:
    app_test = create_app()

    @app_test.get("/echo")
    async def echo(value: int) -> dict[str, int]:
        return {"value": value}

    test_client = TestClient(app_test)
    response = test_client.get("/echo", params={"value": "not-a-number"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "value" in body["message"]


def test_unhandled_error_does_not_leak_traceback() -> None:
    app_test = create_app()

    @app_test.get("/crash")
    async def crash() -> None:
        raise RuntimeError("secret-internal-detail")

    test_client = TestClient(app_test, raise_server_exceptions=False)
    response = test_client.get("/crash")
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert "secret-internal-detail" not in response.text
    assert body["trace_id"]


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
