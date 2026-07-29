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


class AnalysisJobStatusResponse(CamelModel):
    analysis_job_id: uuid.UUID
    status: str
    current_stage: str | None = None
    progress_percent: int
    error_code: str | None = None
    error_message: str | None = None
