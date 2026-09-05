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

    # --- Security ----------------------------------------------------------
    # CORS origins allowed to call the API (frontend dev server).
    cors_origins: list[str] = ["http://localhost:5173"]

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
