from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    internal_token: str = "change-me"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/pitchcoach_analysis"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
