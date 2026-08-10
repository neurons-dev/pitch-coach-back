from __future__ import annotations

import logging
from dataclasses import replace

from app.domain.entities import FeedbackGenerationResult, MetricScoreInput
from app.domain.errors import AnalysisError
from app.domain.feedback_generator import FeedbackGenerator

logger = logging.getLogger(__name__)


class FallbackFeedbackGenerator:
    def __init__(self, *, primary: FeedbackGenerator, fallback: FeedbackGenerator) -> None:
        self._primary = primary
        self._fallback = fallback

    def generate(
        self,
        *,
        transcript_text: str,
        metrics: list[MetricScoreInput],
        overall_score: int,
        presentation_title: str | None = None,
        practice_type_code: str | None = None,
    ) -> FeedbackGenerationResult:
        try:
            return self._primary.generate(
                transcript_text=transcript_text,
                metrics=metrics,
                overall_score=overall_score,
                presentation_title=presentation_title,
                practice_type_code=practice_type_code,
            )
        except AnalysisError as exc:
            logger.warning(
                "feedback generator failed, falling back to template: code=%s", exc.code
            )
            result = self._fallback.generate(
                transcript_text=transcript_text,
                metrics=metrics,
                overall_score=overall_score,
                presentation_title=presentation_title,
                practice_type_code=practice_type_code,
            )
            return replace(result, fallback_reason=exc.code)
