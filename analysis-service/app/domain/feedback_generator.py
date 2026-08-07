from __future__ import annotations

from typing import Protocol

from app.domain.entities import FeedbackGenerationResult, MetricScoreInput


class FeedbackGenerator(Protocol):
    def generate(
        self,
        *,
        transcript_text: str,
        metrics: list[MetricScoreInput],
        overall_score: int,
        presentation_title: str | None = None,
        practice_type_code: str | None = None,
    ) -> FeedbackGenerationResult: ...
