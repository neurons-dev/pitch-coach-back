from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    internal_token: str = "change-me"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/pitchcoach_analysis"
    log_level: str = "INFO"

    worker_poll_interval_seconds: float = 2.0
    watchdog_check_interval_seconds: float = 30.0
    lease_duration_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
