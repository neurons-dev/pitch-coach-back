from __future__ import annotations

import uuid
from dataclasses import dataclass
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
