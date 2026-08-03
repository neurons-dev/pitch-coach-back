from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import delete

_PRODUCTION_HOST_MARKER = "rds.amazonaws.com"

_TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@127.0.0.1:55432/pitchcoach_analysis_test",
)

if _PRODUCTION_HOST_MARKER in _TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL points at what looks like the shared production RDS instance. "
        "Tests claim/complete/fail arbitrary 'queued'/'processing' rows and must never run "
        "against a shared database. Point TEST_DATABASE_URL at a local or dedicated test "
        "database instead."
    )

# app.core.config.get_settings() is @lru_cache'd and app.infrastructure.db.session builds its
# engine at import time, so the test database URL must be in place before either is imported.
os.environ["DATABASE_URL"] = _TEST_DATABASE_URL

from app.core.config import get_settings  # noqa: E402
from app.infrastructure.db.job_repository import SqlAlchemyJobRepository  # noqa: E402
from app.infrastructure.db.models import AnalysisJob  # noqa: E402
from app.infrastructure.db.session import DatabaseSessionProvider  # noqa: E402


@pytest.fixture(scope="session")
def database_session_provider():
    provider = DatabaseSessionProvider(settings=get_settings(), role="api")
    with provider.transaction_scope() as session:
        session.execute(
            delete(AnalysisJob).where(
                AnalysisJob.idempotency_key.like("test-%")
            )
        )
    yield provider
    with provider.transaction_scope() as session:
        session.execute(
            delete(AnalysisJob).where(
                AnalysisJob.idempotency_key.like("test-%")
            )
        )
    provider.dispose()


@pytest.fixture
def job_repository(
    database_session_provider: DatabaseSessionProvider,
) -> SqlAlchemyJobRepository:
    return SqlAlchemyJobRepository(session_provider=database_session_provider)


@pytest.fixture
def make_job(
    job_repository: SqlAlchemyJobRepository,
    database_session_provider: DatabaseSessionProvider,
):
    created_ids: list[uuid.UUID] = []

    def _make_job() -> uuid.UUID:
        creation = job_repository.create_job(
            idempotency_key=f"test-{uuid.uuid4()}",
            session_id=uuid.uuid4(),
            user_id=1,
            audio_object_key="private/test/lease.m4a",
            audio_content_type=None,
            audio_size_bytes=None,
            duration_ms=None,
        )
        created_ids.append(creation.job.id)
        return creation.job.id

    yield _make_job

    with database_session_provider.transaction_scope() as session:
        for job_id in created_ids:
            job = session.get(AnalysisJob, job_id)
            if job is not None:
                session.delete(job)
