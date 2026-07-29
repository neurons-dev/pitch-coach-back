from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.domain.entities import ClaimedJob, JobCreation, JobCreationDisposition
from app.domain.errors import IdempotencyKeyConflictError
from app.infrastructure.db.models import AnalysisJob
from app.infrastructure.db.session import read_session_scope, transaction_scope

_ACTIVE_STATUSES = ("queued", "processing")


class SqlAlchemyJobRepository:
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
    ) -> JobCreation:
        values = {
            "idempotency_key": idempotency_key,
            "session_id": session_id,
            "user_id": user_id,
            "audio_object_key": audio_object_key,
            "audio_content_type": audio_content_type,
            "audio_size_bytes": audio_size_bytes,
            "duration_ms": duration_ms,
            "analysis_version": "v1",
            "status": "queued",
        }
        with transaction_scope() as session:
            statement = (
                insert(AnalysisJob)
                .values(**values)
                .on_conflict_do_nothing()
                .returning(AnalysisJob)
            )
            created_job = session.scalars(statement).one_or_none()
            if created_job is not None:
                return JobCreation(created_job, JobCreationDisposition.CREATED)

            replayed_job = session.scalars(
                select(AnalysisJob).where(AnalysisJob.idempotency_key == idempotency_key)
            ).one_or_none()
            if replayed_job is not None:
                self._ensure_same_request(replayed_job, values)
                return JobCreation(replayed_job, JobCreationDisposition.IDEMPOTENT_REPLAY)

            active_job = session.scalars(
                select(AnalysisJob)
                .where(AnalysisJob.session_id == session_id)
                .where(AnalysisJob.status.in_(_ACTIVE_STATUSES))
                .order_by(AnalysisJob.created_at, AnalysisJob.id)
                .limit(1)
            ).one_or_none()
            if active_job is not None:
                return JobCreation(active_job, JobCreationDisposition.ACTIVE_JOB_REUSED)

            raise RuntimeError("job insert was skipped but no conflicting row is visible")

    @staticmethod
    def _ensure_same_request(job: AnalysisJob, expected: dict[str, object]) -> None:
        request_fields = (
            "session_id",
            "user_id",
            "audio_object_key",
            "audio_content_type",
            "audio_size_bytes",
            "duration_ms",
        )
        mismatches = [name for name in request_fields if getattr(job, name) != expected[name]]
        if mismatches:
            fields = ", ".join(mismatches)
            raise IdempotencyKeyConflictError(
                f"idempotency key was already used with different fields: {fields}"
            )

    def get_job(self, job_id: uuid.UUID) -> AnalysisJob | None:
        with read_session_scope() as session:
            job = session.get(AnalysisJob, job_id)
            if job is not None:
                session.expunge(job)
            return job

    def claim_next_job(self, *, lease_duration_seconds: int) -> ClaimedJob | None:
        with transaction_scope() as session:
            job = session.scalars(
                select(AnalysisJob)
                .where(AnalysisJob.status == "queued")
                .order_by(AnalysisJob.created_at, AnalysisJob.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).one_or_none()

            if job is None:
                return None

            job_id = job.id
            audio_object_key = job.audio_object_key
            analysis_version = job.analysis_version
            lease_token = uuid.uuid4()

            session.execute(
                update(AnalysisJob)
                .where(AnalysisJob.id == job_id)
                .values(
                    status="processing",
                    current_stage="ANALYZING",
                    progress_percent=20,
                    error_code=None,
                    error_message=None,
                    started_at=func.coalesce(AnalysisJob.started_at, func.clock_timestamp()),
                    lease_token=lease_token,
                    lease_expires_at=func.clock_timestamp()
                    + timedelta(seconds=lease_duration_seconds),
                    updated_at=func.clock_timestamp(),
                )
            )

            return ClaimedJob(
                id=job_id,
                audio_object_key=audio_object_key,
                analysis_version=analysis_version,
                lease_token=lease_token,
            )

    def renew_lease(
        self, job_id: uuid.UUID, *, lease_token: uuid.UUID, lease_duration_seconds: int
    ) -> bool:
        with transaction_scope() as session:
            result = session.execute(
                update(AnalysisJob)
                .where(AnalysisJob.id == job_id)
                .where(AnalysisJob.status == "processing")
                .where(AnalysisJob.lease_token == lease_token)
                .values(
                    lease_expires_at=func.clock_timestamp()
                    + timedelta(seconds=lease_duration_seconds),
                    updated_at=func.clock_timestamp(),
                )
            )
            return result.rowcount > 0

    def complete_job(self, job_id: uuid.UUID, *, lease_token: uuid.UUID) -> bool:
        with transaction_scope() as session:
            result = session.execute(
                update(AnalysisJob)
                .where(AnalysisJob.id == job_id)
                .where(AnalysisJob.status == "processing")
                .where(AnalysisJob.lease_token == lease_token)
                .values(
                    status="completed",
                    current_stage="DONE",
                    progress_percent=100,
                    completed_at=func.clock_timestamp(),
                    lease_token=None,
                    lease_expires_at=None,
                    updated_at=func.clock_timestamp(),
                )
            )
            return result.rowcount > 0

    def fail_job(
        self,
        job_id: uuid.UUID,
        *,
        lease_token: uuid.UUID,
        code: str,
        message: str,
        retryable: bool,
    ) -> bool:
        with transaction_scope() as session:
            job = session.scalars(
                select(AnalysisJob)
                .where(AnalysisJob.id == job_id)
                .where(AnalysisJob.status == "processing")
                .where(AnalysisJob.lease_token == lease_token)
                .with_for_update()
            ).one_or_none()
            if job is None:
                return False

            now = datetime.now(timezone.utc)
            job.error_code = code
            job.error_message = message
            job.lease_token = None
            job.lease_expires_at = None
            job.updated_at = now

            if retryable and job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = "queued"
                job.current_stage = "RETRY_PENDING"
            else:
                job.status = "failed"
                job.current_stage = "FAILED"
                job.completed_at = now
            return True

    def requeue_expired_leases(self, *, batch_size: int = 100) -> int:
        with transaction_scope() as session:
            now = datetime.now(timezone.utc)
            stuck_jobs = session.scalars(
                select(AnalysisJob)
                .where(AnalysisJob.status == "processing")
                .where(AnalysisJob.lease_expires_at < func.clock_timestamp())
                .order_by(AnalysisJob.lease_expires_at, AnalysisJob.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            ).all()

            for job in stuck_jobs:
                job.lease_token = None
                job.lease_expires_at = None
                job.updated_at = now
                if job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.status = "queued"
                    job.current_stage = "REQUEUED_AFTER_LEASE_EXPIRY"
                    job.error_code = None
                    job.error_message = None
                else:
                    job.status = "failed"
                    job.current_stage = "FAILED"
                    job.error_code = "LEASE_EXPIRED_RETRY_EXHAUSTED"
                    job.error_message = "Worker lease expired and the retry budget was exhausted."
                    job.completed_at = now

            return len(stuck_jobs)
