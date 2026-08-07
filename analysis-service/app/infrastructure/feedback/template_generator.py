from __future__ import annotations

from app.domain.entities import FeedbackGenerationResult, MetricScoreInput
from app.domain.feedback import build_coach_comment, build_feedback_items

_TEMPLATE_VERSION = "template-feedback-v1"


class TemplateFeedbackGenerator:
    def generate(
        self,
        *,
        transcript_text: str,
        metrics: list[MetricScoreInput],
        overall_score: int,
        presentation_title: str | None = None,
        practice_type_code: str | None = None,
    ) -> FeedbackGenerationResult:
        coach_comment = build_coach_comment(overall_score, metrics)
        feedback_items = build_feedback_items(overall_score, coach_comment, metrics)
        return FeedbackGenerationResult(
            coach_comment=coach_comment,
            feedback_items=feedback_items,
            generator="template",
            prompt_version=_TEMPLATE_VERSION,
        )
