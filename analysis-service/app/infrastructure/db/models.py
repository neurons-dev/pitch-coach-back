from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

_JOB_STATUSES = ("queued", "processing", "completed", "failed", "cancelled")
_ACTIVE_STATUSES = ("queued", "processing")
_METRIC_CODES = ("SPEED", "FILLER", "PRONUNCIATION", "DELIVERY", "STRUCTURE", "FLUENCY")
_FEEDBACK_ITEM_TYPES = ("summary", "strength", "improvement")


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


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        CheckConstraint(
            "overall_score BETWEEN 0 AND 100", name="analysis_results_overall_score_check"
        ),
        CheckConstraint(
            "total_speech_ms IS NULL OR total_speech_ms >= 0",
            name="analysis_results_total_speech_ms_check",
        ),
        CheckConstraint(
            "total_silence_ms IS NULL OR total_silence_ms >= 0",
            name="analysis_results_total_silence_ms_check",
        ),
        CheckConstraint(
            "char_length(trim(pipeline_version)) > 0",
            name="analysis_results_pipeline_version_check",
        ),
        CheckConstraint(
            "char_length(trim(stt_model_version)) > 0",
            name="analysis_results_stt_model_version_check",
        ),
        CheckConstraint(
            "char_length(trim(scoring_rule_version)) > 0",
            name="analysis_results_scoring_rule_version_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    overall_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    coach_comment: Mapped[str | None] = mapped_column(Text)
    transcript_text: Mapped[str | None] = mapped_column(Text)
    transcript_segments: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    total_speech_ms: Mapped[int | None] = mapped_column(BigInteger)
    total_silence_ms: Mapped[int | None] = mapped_column(BigInteger)

    pipeline_version: Mapped[str] = mapped_column(String, nullable=False)
    stt_model_version: Mapped[str] = mapped_column(String, nullable=False)
    scoring_rule_version: Mapped[str] = mapped_column(String, nullable=False)

    model_info: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    analyzed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    metric_scores: Mapped[list["AnalysisMetricScore"]] = relationship(
        back_populates="result",
        cascade="all, delete-orphan",
        order_by="AnalysisMetricScore.id",
        lazy="raise",
    )
    feedback_items: Mapped[list["FeedbackItem"]] = relationship(
        back_populates="result",
        cascade="all, delete-orphan",
        order_by="FeedbackItem.sort_order",
        lazy="raise",
    )


class AnalysisMetricScore(Base):
    __tablename__ = "analysis_metric_scores"
    __table_args__ = (
        UniqueConstraint(
            "analysis_result_id",
            "metric_code",
            name="analysis_metric_scores_analysis_result_id_metric_code_key",
        ),
        CheckConstraint(
            f"metric_code IN {_METRIC_CODES}", name="analysis_metric_scores_metric_code_check"
        ),
        CheckConstraint("score BETWEEN 0 AND 100", name="analysis_metric_scores_score_check"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_results.id", ondelete="CASCADE"), nullable=False
    )
    metric_code: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    raw_value: Mapped[float | None] = mapped_column(Numeric(12, 3))
    unit: Mapped[str | None] = mapped_column(String)
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    result: Mapped[AnalysisResult] = relationship(back_populates="metric_scores")


class FeedbackItem(Base):
    __tablename__ = "feedback_items"
    __table_args__ = (
        CheckConstraint(
            f"item_type IN {_FEEDBACK_ITEM_TYPES}", name="feedback_items_item_type_check"
        ),
        CheckConstraint(
            f"metric_code IS NULL OR metric_code IN {_METRIC_CODES}",
            name="feedback_items_metric_code_check",
        ),
        CheckConstraint("char_length(trim(title)) > 0", name="feedback_items_title_check"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_results.id", ondelete="CASCADE"), nullable=False
    )
    metric_code: Mapped[str | None] = mapped_column(String)
    item_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    result: Mapped[AnalysisResult] = relationship(back_populates="feedback_items")
