"""Security-sensitive configuration validation."""

import pytest
from app.core.config import Settings
from pydantic import ValidationError


@pytest.mark.parametrize(
    ("secret_key", "registration_token"),
    [
        ("development-only-secret-key-0123456789abcdef-XY", "real-invite-token-123"),
        ("replace-with-a-long-random-secret-key-value", "real-invite-token-123"),
        ("a-real-secret-key-that-is-at-least-32-characters", None),
        ("a-real-secret-key-that-is-at-least-32-characters", "replace-with-token"),
    ],
)
def test_production_rejects_default_or_missing_secrets(
    secret_key: str, registration_token: str | None
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            secret_key=secret_key,
            registration_token=registration_token,
        )


def test_production_accepts_strong_non_default_secrets() -> None:
    config = Settings(
        app_env="production",
        secret_key="a-real-secret-key-that-is-at-least-32-characters",
        registration_token="a-real-registration-token",
    )
    assert config.app_env == "production"


def test_local_demo_anchors_sqlite_path_and_disables_queue() -> None:
    from pathlib import Path

    from app.core.config import BACKEND_DIR
    from sqlalchemy.engine import make_url

    config = Settings(
        local_demo=True,
        database_url="sqlite+aiosqlite:///./data/demo.sqlite3",
        data_dir="./data/demo",
        statement_import_async=True,
    )
    assert Path(make_url(config.database_url).database) == BACKEND_DIR / "data/demo.sqlite3"
    assert Path(config.data_dir) == BACKEND_DIR / "data/demo"
    assert config.statement_import_async is False


@pytest.mark.parametrize(
    "url", ["sqlite+aiosqlite:///:memory:", "postgresql+asyncpg://localhost/db"]
)
def test_local_demo_rejects_non_persistent_or_non_sqlite_database(url) -> None:
    with pytest.raises(ValidationError):
        Settings(local_demo=True, database_url=url)


def test_production_rejects_local_demo() -> None:
    with pytest.raises(ValidationError):
        Settings(local_demo=True, app_env="production")
