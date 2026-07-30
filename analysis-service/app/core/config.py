from __future__ import annotations

from functools import lru_cache
from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    _PRODUCTION_CAPACITY_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "api_db_pool_size",
            "api_db_max_overflow",
            "worker_db_pool_size",
            "worker_db_max_overflow",
            "api_instance_count",
            "worker_instance_count",
            "postgres_max_connections",
            "postgres_reserved_connections",
        }
    )

    app_environment: Literal["local", "test", "staging", "production"] = "local"
    internal_token: str = "change-me"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/pitchcoach_analysis"
    log_level: str = "INFO"

    worker_poll_interval_seconds: float = Field(default=2.0, gt=0)
    watchdog_check_interval_seconds: float = Field(default=30.0, gt=0)
    lease_duration_seconds: int = Field(default=300, gt=0)
    lease_heartbeat_interval_seconds: float = Field(default=60.0, gt=0)

    api_db_pool_size: int = Field(default=5, ge=1)
    api_db_max_overflow: int = Field(default=5, ge=0)
    worker_db_pool_size: int = Field(default=3, ge=1)
    worker_db_max_overflow: int = Field(default=2, ge=0)
    db_pool_timeout_seconds: float = Field(default=5.0, gt=0)
    db_pool_recycle_seconds: int = Field(default=1800, gt=0)

    db_statement_timeout_ms: int = Field(default=30_000, gt=0)
    db_lock_timeout_ms: int = Field(default=5_000, gt=0)
    db_idle_in_transaction_session_timeout_ms: int = Field(default=60_000, gt=0)

    api_instance_count: int = Field(default=1, ge=1)
    worker_instance_count: int = Field(default=1, ge=1)
    postgres_max_connections: int = Field(default=100, ge=1)
    postgres_reserved_connections: int = Field(default=10, ge=0)

    watchdog_batch_size: int = Field(default=100, ge=1)
    watchdog_max_batches_per_cycle: int = Field(default=10, ge=1)
    watchdog_max_run_seconds: float = Field(default=10.0, gt=0)

    pipeline_version: str = "audio-pipeline-v1"

    aws_region: str = "ap-northeast-2"
    s3_bucket: str = "pitch-coach-bucket"
    audio_download_timeout_seconds: float = Field(default=30.0, gt=0)
    audio_max_size_bytes: int = Field(default=100_000_000, gt=0)
    audio_max_duration_ms: int = Field(default=600_000, gt=0)

    whisper_model_size: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    stt_timeout_seconds: float = Field(default=120.0, gt=0)

    def db_pool_size(self, role: Literal["api", "worker"]) -> int:
        if role == "api":
            return self.api_db_pool_size
        return self.worker_db_pool_size

    def db_max_overflow(self, role: Literal["api", "worker"]) -> int:
        if role == "api":
            return self.api_db_max_overflow
        return self.worker_db_max_overflow

    @property
    def planned_database_connections(self) -> int:
        api_connections = self.api_instance_count * (
            self.api_db_pool_size + self.api_db_max_overflow
        )
        worker_connections = self.worker_instance_count * (
            self.worker_db_pool_size + self.worker_db_max_overflow
        )
        return api_connections + worker_connections

    @property
    def usable_database_connections(self) -> int:
        return self.postgres_max_connections - self.postgres_reserved_connections

    @model_validator(mode="after")
    def validate_operational_limits(self) -> Self:
        if self.app_environment in {"staging", "production"}:
            missing_capacity_fields = (
                self._PRODUCTION_CAPACITY_FIELDS - self.model_fields_set
            )
            if missing_capacity_fields:
                missing = ", ".join(sorted(missing_capacity_fields))
                raise ValueError(
                    "staging/production requires explicit database capacity "
                    f"settings: {missing}"
                )
        if self.lease_heartbeat_interval_seconds >= self.lease_duration_seconds:
            raise ValueError(
                "LEASE_HEARTBEAT_INTERVAL_SECONDS must be shorter than "
                "LEASE_DURATION_SECONDS"
            )
        if self.db_pool_timeout_seconds >= self.watchdog_max_run_seconds:
            raise ValueError(
                "DB_POOL_TIMEOUT_SECONDS must be shorter than "
                "WATCHDOG_MAX_RUN_SECONDS"
            )
        if self.usable_database_connections <= 0:
            raise ValueError(
                "POSTGRES_RESERVED_CONNECTIONS must be smaller than "
                "POSTGRES_MAX_CONNECTIONS"
            )
        if self.planned_database_connections >= self.usable_database_connections:
            raise ValueError(
                "planned database connections must be smaller than available PostgreSQL "
                "connections: "
                f"planned={self.planned_database_connections}, "
                f"available={self.usable_database_connections}"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
