from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

_JOB_STATUSES = ("queued", "processing", "completed", "failed", "cancelled")
_ACTIVE_STATUSES = ("queued", "processing")


class Base(DeclarativeBase):
    pass


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        CheckConstraint(f"status IN {_JOB_STATUSES}", name="analysis_jobs_status_check"),
        CheckConstraint(
            "progress_percent BETWEEN 0 AND 100", name="analysis_jobs_progress_percent_check"
        ),
        CheckConstraint("retry_count >= 0", name="analysis_jobs_retry_count_check"),
        CheckConstraint("max_retries >= 0", name="analysis_jobs_max_retries_check"),
        CheckConstraint(
            "audio_size_bytes IS NULL OR audio_size_bytes >= 0",
            name="analysis_jobs_audio_size_bytes_check",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="analysis_jobs_duration_ms_check"
        ),
        UniqueConstraint("idempotency_key", name="analysis_jobs_idempotency_key_key"),
        Index("idx_analysis_jobs_session_created", "session_id", "created_at"),
        Index("idx_analysis_jobs_user_created", "user_id", "created_at"),
        Index(
            "idx_analysis_jobs_claim",
            "created_at",
            "id",
            postgresql_where=text("status = 'queued'"),
        ),
        Index(
            "idx_analysis_jobs_expired_lease",
            "lease_expires_at",
            "id",
            postgresql_where=text("status = 'processing'"),
        ),
        Index(
            "uq_analysis_jobs_active_session",
            "session_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'processing')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    audio_object_key: Mapped[str] = mapped_column(String, nullable=False)
    audio_content_type: Mapped[str | None] = mapped_column(String)
    audio_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)

    analysis_version: Mapped[str] = mapped_column(String, nullable=False, server_default="v1")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="queued")
    current_stage: Mapped[str | None] = mapped_column(String)
    progress_percent: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")

    retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    max_retries: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="3")
    error_code: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)

    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
