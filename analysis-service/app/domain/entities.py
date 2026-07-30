from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol


class AnalysisJobLike(Protocol):
    id: uuid.UUID
    status: str
    current_stage: str | None
    progress_percent: int
    error_code: str | None
    error_message: str | None
    audio_object_key: str
    analysis_version: str
    retry_count: int
    max_retries: int
    created_at: datetime


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    audio_object_key: str
    analysis_version: str
    lease_token: uuid.UUID


class JobCreationDisposition(str, Enum):
    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    ACTIVE_JOB_REUSED = "active_job_reused"


@dataclass(frozen=True)
class JobCreation:
    job: AnalysisJobLike
    disposition: JobCreationDisposition

    @property
    def created(self) -> bool:
        return self.disposition is JobCreationDisposition.CREATED


@dataclass(frozen=True)
class MetricScoreInput:
    metric_code: str
    score: int
    raw_value: float | None = None
    unit: str | None = None
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FeedbackItemInput:
    item_type: str
    title: str
    description: str
    metric_code: str | None = None
    evidence: dict = field(default_factory=dict)
    sort_order: int = 0


@dataclass(frozen=True)
class AnalysisResultInput:
    overall_score: int
    pipeline_version: str
    stt_model_version: str
    scoring_rule_version: str
    coach_comment: str | None = None
    transcript_text: str | None = None
    transcript_segments: list[dict] = field(default_factory=list)
    total_speech_ms: int | None = None
    total_silence_ms: int | None = None
    model_info: dict = field(default_factory=dict)
    metric_scores: list[MetricScoreInput] = field(default_factory=list)
    feedback_items: list[FeedbackItemInput] = field(default_factory=list)
