from __future__ import annotations

import uuid

from app.interface.schemas.common import CamelModel


class AnalysisJobCreateRequest(CamelModel):
    session_id: uuid.UUID
    user_id: int
    audio_object_key: str
    audio_content_type: str | None = None
    audio_size_bytes: int | None = None
    duration_ms: int | None = None


class AnalysisJobCreateResponse(CamelModel):
    analysis_job_id: uuid.UUID
    status: str


class MetricScoreOut(CamelModel):
    metric_code: str
    score: int
    raw_value: float | None = None
    unit: str | None = None


class FeedbackItemOut(CamelModel):
    item_type: str
    title: str
    description: str
    metric_code: str | None = None
    sort_order: int


class AnalysisResultOut(CamelModel):
    overall_score: int
    coach_comment: str | None = None
    metric_scores: list[MetricScoreOut]
    feedback_items: list[FeedbackItemOut]


class AnalysisJobStatusResponse(CamelModel):
    analysis_job_id: uuid.UUID
    status: str
    current_stage: str | None = None
    progress_percent: int
    error_code: str | None = None
    error_message: str | None = None
    result: AnalysisResultOut | None = None
