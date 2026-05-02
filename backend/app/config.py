"""Runtime configuration for the VidyutDrishti backend.

Uses pydantic-settings; all values can be overridden via environment
variables (see infra/.env.sample).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VidyutDrishti"
    app_env: str = Field(default="dev", description="dev | test | prod")
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database - credentials have NO defaults; they must come from the
    # environment (infra/.env) so no real deployment ever boots with a
    # hardcoded password baked into the image.
    db_host: str = "timescaledb"
    db_port: int = 5432
    db_name: str = Field(..., description="Postgres database name (env: DB_NAME)")
    db_user: str = Field(..., description="Postgres role (env: DB_USER)")
    db_password: str = Field(..., description="Postgres password (env: DB_PASSWORD)")

    # Simulator
    simulator_seed: int = 42
    simulator_days: int = 180
    simulator_dt_count: int = 2
    simulator_meters_per_dt: int = 30

    # Feature flags
    enable_recalibration: bool = True

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
