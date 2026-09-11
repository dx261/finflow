"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the FinFlow backend.

    Values are read from environment variables (or a ``.env`` file when it
    exists in the working directory). All variables are optional and fall
    back to development-friendly defaults so the API can boot without a full
    infrastructure stack.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -----------------------------------------------------
    app_name: str = "FinFlow"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = False

    api_v1_prefix: str = "/api/v1"

    # --- Database ------------------------------------------------------------
    # Async SQLAlchemy connection string. Production uses PostgreSQL via
    # asyncpg; tests override this with SQLite (aiosqlite) so the suite runs
    # without a database server.
    database_url: str = "postgresql+asyncpg://finflow:finflow@localhost:5432/finflow"
    # Connection pool strategy: "queue" (default) or "null". Tests use "null"
    # so connections are never reused across event loops.
    database_poolclass: str = "queue"

    # --- Redis ----------------------------------------------------------------
    # Used as Celery broker/results, cache, distributed locks and
    # idempotency store. Tests override this to an unreachable port so the
    # suite never depends on a running Redis server.
    # 127.0.0.1 (not "localhost") avoids IPv6 ::1 resolution issues with
    # the kombu broker on Windows.
    redis_url: str = "redis://127.0.0.1:6379/0"

    # --- Async processing ------------------------------------------------------
    # When true, statement uploads are dispatched to the Celery worker.
    # Disable in tests / single-process dev where the sync path is used.
    statement_import_async: bool = True

    # --- Reconciliation -----------------------------------------------------
    # Weights and thresholds for payment-to-transaction matching (§43).
    recon_amount_weight: float = 0.45
    recon_account_weight: float = 0.20
    recon_date_weight: float = 0.15
    recon_counterparty_weight: float = 0.15
    recon_reference_weight: float = 0.05
    auto_match_threshold: float = 0.80
    review_threshold: float = 0.60

    # --- Security ----------------------------------------------------------
    # CORS origins allowed to call the API (frontend dev server).
    cors_origins: list[str] = ["http://localhost:5173"]

    # Development-only default. Override with a strong random value in
    # production (>= 32 bytes for HS256).
    secret_key: str = "development-only-secret-key-0123456789abcdef-XY"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # --- Storage -------------------------------------------------------------
    # Root directory for uploaded statement files, exports and temp data.
    data_dir: str = "./data"
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 20

    @property
    def uploads_path(self) -> str:
        """Absolute path where uploaded statement files are stored."""
        from pathlib import Path

        return str(Path(self.data_dir) / self.upload_dir)


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()


settings = get_settings()
