"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for the FinFlow backend.

    Values are read from environment variables (or a ``.env`` file when it
    exists in the working directory). All variables are optional and fall
    back to development-friendly defaults so the API can boot without a full
    infrastructure stack.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -----------------------------------------------------
    app_name: str = "FinFlow"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = False
    # Explicit opt-in: anonymous visitors share a separate demo principal.
    demo_mode: bool = False
    # Local SQLite showcase: no Docker, Redis, worker or beat required.
    local_demo: bool = False

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
    # Shared invite/bootstrap token required for registration in production.
    registration_token: str | None = None

    # --- Storage -------------------------------------------------------------
    # Root directory for uploaded statement files, exports and temp data.
    data_dir: str = "./data"
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 20

    # Limit the search window used by automatic reconciliation.  Keeping
    # this bounded avoids matching a new payment to an unrelated old debit.
    recon_candidate_window_days: int = 30

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Fail closed when production is started with placeholder secrets."""
        if self.local_demo:
            if self.app_env.lower() == "production":
                raise ValueError("LOCAL_DEMO must be disabled in production")
            url = make_url(self.database_url)
            if (
                url.drivername != "sqlite+aiosqlite"
                or not url.database
                or url.database == ":memory:"
            ):
                raise ValueError("LOCAL_DEMO requires a persistent sqlite+aiosqlite database")
            # Anchor relative paths to the backend, never the shell's cwd.
            db_path = Path(url.database)
            if not db_path.is_absolute():
                db_path = BACKEND_DIR / db_path
            self.database_url = url.set(database=db_path.resolve().as_posix()).render_as_string()
            if not Path(self.data_dir).is_absolute():
                self.data_dir = str((BACKEND_DIR / self.data_dir).resolve())
            self.statement_import_async = False
        if self.app_env.lower() != "production":
            return self
        if len(self.secret_key) < 32 or self.secret_key.startswith(
            ("development-only", "replace-with")
        ):
            raise ValueError("SECRET_KEY must be a non-default value of at least 32 characters")
        if (
            not self.registration_token
            or self.registration_token.startswith("replace-with")
            or len(self.registration_token) < 16
        ):
            raise ValueError("REGISTRATION_TOKEN must be at least 16 characters in production")
        return self

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
