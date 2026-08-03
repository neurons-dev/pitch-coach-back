from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import TimeoutError as SqlAlchemyTimeoutError

from app.application.workers.dispatcher import Dispatcher
from app.core.config import Settings
from app.domain.entities import AnalysisResultInput
from app.domain.errors import RepositoryTimeoutError
from app.infrastructure.db import session as session_module
from app.infrastructure.db.job_repository import SqlAlchemyJobRepository
from app.infrastructure.db.session import DatabaseSessionProvider


def _settings(**overrides) -> Settings:
    values = {
        "database_url": "postgresql+psycopg://postgres:postgres@localhost/test",
        "api_db_pool_size": 4,
        "api_db_max_overflow": 2,
        "worker_db_pool_size": 2,
        "worker_db_max_overflow": 1,
        "api_instance_count": 1,
        "worker_instance_count": 1,
        "postgres_max_connections": 30,
        "postgres_reserved_connections": 10,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_api_and_worker_use_separate_pool_limits(monkeypatch):
    # given
    engine_calls: list[dict] = []
    fake_pool = SimpleNamespace(
        size=lambda: 0,
        checkedin=lambda: 0,
        checkedout=lambda: 0,
        overflow=lambda: 0,
    )

    def fake_create_engine(_url, **kwargs):
        engine_calls.append(kwargs)
        return SimpleNamespace(pool=fake_pool)

    monkeypatch.setattr(session_module, "create_engine", fake_create_engine)
    settings = _settings()

    # when
    DatabaseSessionProvider(settings=settings, role="api")
    DatabaseSessionProvider(settings=settings, role="worker")

    # then
    assert engine_calls[0]["pool_size"] == 4
    assert engine_calls[0]["max_overflow"] == 2
    assert engine_calls[1]["pool_size"] == 2
    assert engine_calls[1]["max_overflow"] == 1
    assert engine_calls[0]["pool_timeout"] == settings.db_pool_timeout_seconds
    assert engine_calls[0]["pool_recycle"] == settings.db_pool_recycle_seconds
    assert "statement_timeout=30000" in engine_calls[0]["connect_args"]["options"]
    assert "lock_timeout=5000" in engine_calls[0]["connect_args"]["options"]
    assert (
        "idle_in_transaction_session_timeout=60000"
        in engine_calls[0]["connect_args"]["options"]
    )


def test_settings_reject_connection_plan_that_exhausts_postgres():
    # given
    unsafe_values = {
        "api_db_pool_size": 3,
        "api_db_max_overflow": 2,
        "worker_db_pool_size": 2,
        "worker_db_max_overflow": 1,
        "postgres_max_connections": 10,
        "postgres_reserved_connections": 2,
    }

    # when / then
    with pytest.raises(ValidationError, match="planned database connections"):
        _settings(**unsafe_values)


def test_production_requires_explicit_database_capacity_settings():
    # given / when / then
    with pytest.raises(
        ValidationError,
        match="requires explicit database capacity settings",
    ):
        Settings(
            _env_file=None,
            app_environment="production",
            database_url="postgresql+psycopg://postgres:postgres@localhost/test",
        )


def test_production_accepts_explicit_database_capacity_settings():
    # given / when
    settings = _settings(app_environment="production")

    # then
    assert settings.planned_database_connections == 9
    assert settings.usable_database_connections == 20


def test_settings_reject_heartbeat_that_can_outlive_lease():
    # given / when / then
    with pytest.raises(ValidationError, match="must be shorter"):
        _settings(
            lease_duration_seconds=30,
            lease_heartbeat_interval_seconds=30,
        )


def test_settings_reject_pool_wait_longer_than_watchdog_cycle():
    # given / when / then
    with pytest.raises(ValidationError, match="must be shorter"):
        _settings(
            db_pool_timeout_seconds=10,
            watchdog_max_run_seconds=10,
        )


def test_watchdog_repository_translates_pool_timeout():
    # given
    class _TimedOutSessionProvider:
        @contextmanager
        def transaction_scope(self):
            raise SqlAlchemyTimeoutError("pool exhausted")
            yield

    repository = SqlAlchemyJobRepository(
        session_provider=_TimedOutSessionProvider()
    )

    # when / then
    with pytest.raises(RepositoryTimeoutError, match="acquiring"):
        repository.requeue_expired_leases(
            batch_size=100,
            timeout_seconds=1,
        )


def test_analysis_runner_does_not_hold_database_connection(
    job_repository,
    make_job,
    database_session_provider,
):
    # given
    make_job()
    checked_out_during_analysis: list[int] = []

    def run_analysis(**_):
        checked_out_during_analysis.append(
            database_session_provider.pool_snapshot()["checked_out"]
        )
        return AnalysisResultInput(
            overall_score=80,
            pipeline_version="audio-pipeline-v1",
            stt_model_version="faster-whisper-tiny",
            scoring_rule_version="coach-ko-v1",
        )

    dispatcher = Dispatcher(
        job_repository=job_repository,
        lease_duration_seconds=300,
        worker_poll_interval_seconds=2,
        lease_heartbeat_interval_seconds=60,
        analysis_runner=run_analysis,
    )

    # when
    processed = dispatcher._process_next(
        lease_duration_seconds=300,
        heartbeat_interval_seconds=60,
    )

    # then
    assert processed is True
    assert checked_out_during_analysis == [0]
