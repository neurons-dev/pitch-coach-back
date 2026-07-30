from __future__ import annotations

from typing import cast

from fastapi import Request

from app.domain.repositories import JobRepository


def get_job_repository(request: Request) -> JobRepository:
    return cast(JobRepository, request.app.state.job_repository)
