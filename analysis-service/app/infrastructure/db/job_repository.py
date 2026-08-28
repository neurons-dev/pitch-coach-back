from __future__ import annotations

import math
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, TimeoutError as SqlAlchemyTimeoutError
from sqlalchemy.orm import joinedload, selectinload

from app.domain.entities import AnalysisResultInput, ClaimedJob, JobCreation, JobCreationDisposition
from app.domain.errors import IdempotencyKeyConflictError, RepositoryTimeoutError
from app.infrastructure.db.models import AnalysisJob, AnalysisMetricScore, AnalysisResult, FeedbackItem
from app.infrastructure.db.session import DatabaseSessionProvider

_ACTIVE_STATUSES = ("queued", "processing")


class SqlAlchemyJobRepository:
    def __init__(self, *, session_provider: DatabaseSessionProvider) -> None:
        self._db = session_provider

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
        presentation_title: str | None = None,
        practice_type_code: str | None = None,
        target_duration_sec: int | None = None,
    ) -> JobCreation:
        values = {
            "idempotency_key": idempotency_key,
            "session_id": session_id,
            "user_id": user_id,
            "audio_object_key": audio_object_key,
            "audio_content_type": audio_content_type,
            "audio_size_bytes": audio_size_bytes,
            "duration_ms": duration_ms,
            "presentation_title": presentation_title,
            "practice_type_code": practice_type_code,
            "target_duration_sec": target_duration_sec,
            "analysis_version": "v1",
            "status": "queued",
        }
        with self._db.transaction_scope() as session:
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
            "presentation_title",
            "practice_type_code",
            "target_duration_sec",
        )
        mismatches = [name for name in request_fields if getattr(job, name) != expected[name]]
        if mismatches:
            fields = ", ".join(mismatches)
            raise IdempotencyKeyConflictError(
                f"idempotency key was already used with different fields: {fields}"
            )

    def get_job(self, job_id: uuid.UUID) -> AnalysisJob | None:
        with self._db.read_session_scope() as session:
            job = session.scalars(
                select(AnalysisJob)
                .where(AnalysisJob.id == job_id)
                .options(
                    joinedload(AnalysisJob.result).selectinload(AnalysisResult.metric_scores),
                    joinedload(AnalysisJob.result).selectinload(AnalysisResult.feedback_items),
                )
            ).one_or_none()
            if job is not None:
                session.expunge(job)
            return job

    def claim_next_job(self, *, lease_duration_seconds: int) -> ClaimedJob | None:
        with self._db.transaction_scope() as session:
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
            presentation_title = job.presentation_title
            practice_type_code = job.practice_type_code
            target_duration_sec = job.target_duration_sec
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
                presentation_title=presentation_title,
                practice_type_code=practice_type_code,
                target_duration_sec=target_duration_sec,
            )

    def renew_lease(
        self, job_id: uuid.UUID, *, lease_token: uuid.UUID, lease_duration_seconds: int
    ) -> bool:
        with self._db.transaction_scope() as session:
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

    def update_progress(
        self,
        job_id: uuid.UUID,
        *,
        lease_token: uuid.UUID,
        stage: str,
        progress_percent: int,
    ) -> bool:
        with self._db.transaction_scope() as session:
            result = session.execute(
                update(AnalysisJob)
                .where(AnalysisJob.id == job_id)
                .where(AnalysisJob.status == "processing")
                .where(AnalysisJob.lease_token == lease_token)
                .values(
                    current_stage=stage,
                    progress_percent=progress_percent,
                    updated_at=func.clock_timestamp(),
                )
            )
            return result.rowcount > 0

    def complete_job(self, job_id: uuid.UUID, *, lease_token: uuid.UUID) -> bool:
        with self._db.transaction_scope() as session:
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

    def save_result_and_complete(
        self,
        job_id: uuid.UUID,
        *,
        lease_token: uuid.UUID,
        result: AnalysisResultInput,
    ) -> bool:
        with self._db.transaction_scope() as session:
            job = session.scalars(
                select(AnalysisJob)
                .where(AnalysisJob.id == job_id)
                .where(AnalysisJob.status == "processing")
                .where(AnalysisJob.lease_token == lease_token)
                .with_for_update()
            ).one_or_none()
            if job is None:
                return False

            job.result = AnalysisResult(
                overall_score=result.overall_score,
                coach_comment=result.coach_comment,
                transcript_text=result.transcript_text,
                transcript_segments=result.transcript_segments,
                total_speech_ms=result.total_speech_ms,
                total_silence_ms=result.total_silence_ms,
                pipeline_version=result.pipeline_version,
                stt_model_version=result.stt_model_version,
                scoring_rule_version=result.scoring_rule_version,
                model_info=result.model_info,
                metric_scores=[
                    AnalysisMetricScore(
                        metric_code=metric.metric_code,
                        score=metric.score,
                        raw_value=metric.raw_value,
                        unit=metric.unit,
                        details=metric.details,
                    )
                    for metric in result.metric_scores
                ],
                feedback_items=[
                    FeedbackItem(
                        metric_code=item.metric_code,
                        item_type=item.item_type,
                        title=item.title,
                        description=item.description,
                        evidence=item.evidence,
                        sort_order=item.sort_order,
                    )
                    for item in result.feedback_items
                ],
            )

            now = datetime.now(timezone.utc)
            job.status = "completed"
            job.current_stage = "DONE"
            job.progress_percent = 100
            job.completed_at = now
            job.lease_token = None
            job.lease_expires_at = None
            job.updated_at = now
            return True

    def fail_job(
        self,
        job_id: uuid.UUID,
        *,
        lease_token: uuid.UUID,
        code: str,
        message: str,
        retryable: bool,
    ) -> bool:
        with self._db.transaction_scope() as session:
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

    def requeue_expired_leases(
        self,
        *,
        batch_size: int = 100,
        timeout_seconds: float | None = None,
    ) -> int:
        operation_started_at = time.monotonic()
        try:
            with self._db.transaction_scope() as session:
                if timeout_seconds is not None:
                    session.connection()
                    remaining_seconds = timeout_seconds - (
                        time.monotonic() - operation_started_at
                    )
                    if remaining_seconds <= 0:
                        raise RepositoryTimeoutError(
                            "requeue operation exhausted its time budget "
                            "while acquiring a database connection"
                        )
                    statement_timeout_ms = max(
                        1,
                        math.ceil(remaining_seconds * 1000),
                    )
                    session.execute(
                        text(
                            "SELECT set_config("
                            "'statement_timeout', :statement_timeout, true)"
                        ),
                        {"statement_timeout": f"{statement_timeout_ms}ms"},
                    )

                expired_jobs = (
                    select(AnalysisJob.id)
                    .where(AnalysisJob.status == "processing")
                    .where(
                        AnalysisJob.lease_expires_at
                        < func.statement_timestamp()
                    )
                    .order_by(AnalysisJob.lease_expires_at, AnalysisJob.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                    .cte("expired_jobs")
                )
                retryable = AnalysisJob.retry_count < AnalysisJob.max_retries
                requeued_ids = session.scalars(
                    update(AnalysisJob)
                    .where(AnalysisJob.id.in_(select(expired_jobs.c.id)))
                    .values(
                        lease_token=None,
                        lease_expires_at=None,
                        updated_at=func.clock_timestamp(),
                        retry_count=case(
                            (retryable, AnalysisJob.retry_count + 1),
                            else_=AnalysisJob.retry_count,
                        ),
                        status=case((retryable, "queued"), else_="failed"),
                        current_stage=case(
                            (retryable, "REQUEUED_AFTER_LEASE_EXPIRY"),
                            else_="FAILED",
                        ),
                        error_code=case(
                            (retryable, None),
                            else_="LEASE_EXPIRED_RETRY_EXHAUSTED",
                        ),
                        error_message=case(
                            (retryable, None),
                            else_="Worker lease expired and the retry budget was exhausted.",
                        ),
                        completed_at=case(
                            (retryable, AnalysisJob.completed_at),
                            else_=func.clock_timestamp(),
                        ),
                    )
                    .returning(AnalysisJob.id)
                ).all()
                return len(requeued_ids)
        except SqlAlchemyTimeoutError as exc:
            raise RepositoryTimeoutError(
                "requeue operation timed out while acquiring a database connection"
            ) from exc
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) == "57014":
                raise RepositoryTimeoutError(
                    "requeue operation exceeded its statement timeout"
                ) from exc
            raise
