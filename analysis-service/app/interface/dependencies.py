from __future__ import annotations

from app.domain.repositories import JobRepository
from app.infrastructure.db.job_repository import SqlAlchemyJobRepository

_job_repository = SqlAlchemyJobRepository()


def get_job_repository() -> JobRepository:
    return _job_repository
