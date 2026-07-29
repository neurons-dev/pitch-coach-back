from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

from app.domain.entities import JobCreation, JobCreationDisposition
from app.domain.errors import IdempotencyKeyConflictError
from app.infrastructure.db.models import AnalysisJob
from app.infrastructure.db.session import SessionLocal

_ACTIVE_STATUSES = ("queued", "processing")


class SqlAlchemyJobRepository:
    """JobRepository의 SQLAlchemy 구현체. 트랜잭션 경계를 스스로 관리한다."""

    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self._session_factory = session_factory

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
        with self._session_factory.begin() as session:
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
        with self._session_factory() as session:
            job = session.get(AnalysisJob, job_id)
            if job is not None:
                session.expunge(job)
            return job

    def claim_next_job(self, *, lease_duration_seconds: int) -> AnalysisJob | None:
        with self._session_factory.begin() as session:
            job = session.scalars(
                select(AnalysisJob)
                .where(AnalysisJob.status == "queued")
                .order_by(AnalysisJob.created_at, AnalysisJob.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).one_or_none()

            if job is None:
                return None

            now = datetime.now(timezone.utc)
            job.status = "processing"
            job.current_stage = "ANALYZING"
            job.progress_percent = 20
            job.error_code = None
            job.error_message = None
            job.started_at = job.started_at or now
            job.lease_expires_at = now + timedelta(seconds=lease_duration_seconds)
            job.updated_at = now
            session.flush()
            session.expunge(job)
            return job

    def complete_job(self, job_id: uuid.UUID) -> bool:
        with self._session_factory.begin() as session:
            job = session.get(AnalysisJob, job_id)
            if job is None:
                return False
            now = datetime.now(timezone.utc)
            job.status = "completed"
            job.current_stage = "DONE"
            job.progress_percent = 100
            job.completed_at = now
            job.lease_expires_at = None
            job.updated_at = now
            return True

    def fail_job(
        self, job_id: uuid.UUID, *, code: str, message: str, retryable: bool
    ) -> bool:
        with self._session_factory.begin() as session:
            job = session.get(AnalysisJob, job_id)
            if job is None:
                return False

            now = datetime.now(timezone.utc)
            job.error_code = code
            job.error_message = message
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
        with self._session_factory.begin() as session:
            now = datetime.now(timezone.utc)
            stuck_jobs = session.scalars(
                select(AnalysisJob)
                .where(AnalysisJob.status == "processing")
                .where(AnalysisJob.lease_expires_at < now)
                .order_by(AnalysisJob.lease_expires_at, AnalysisJob.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            ).all()

            for job in stuck_jobs:
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
