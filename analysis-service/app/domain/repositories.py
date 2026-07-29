from __future__ import annotations

import uuid
from typing import Protocol

from app.domain.entities import AnalysisJobLike, ClaimedJob, JobCreation


class JobRepository(Protocol):
    def create_job(
        self,
        *,
        idempotency_key: str,
        session_id: uuid.UUID,
        user_id: int,
        audio_object_key: str,
        audio_content_type: str | None,
        audio_size_bytes: int | None,
        duration_ms: int | None,
    ) -> JobCreation: ...

    def get_job(self, job_id: uuid.UUID) -> AnalysisJobLike | None: ...

    def claim_next_job(self, *, lease_duration_seconds: int) -> ClaimedJob | None: ...

    def renew_lease(
        self, job_id: uuid.UUID, *, lease_token: uuid.UUID, lease_duration_seconds: int
    ) -> bool: ...

    def complete_job(self, job_id: uuid.UUID, *, lease_token: uuid.UUID) -> bool: ...

    def fail_job(
        self,
        job_id: uuid.UUID,
        *,
        lease_token: uuid.UUID,
        code: str,
        message: str,
        retryable: bool,
    ) -> bool: ...

    def requeue_expired_leases(self, *, batch_size: int = 100) -> int: ...
