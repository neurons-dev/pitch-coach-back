from __future__ import annotations

from app.core.config import Settings
from app.domain.feedback_generator import FeedbackGenerator


def create_feedback_generator(settings: Settings) -> FeedbackGenerator:
    if not settings.openai_api_key:
        raise ValueError(
            "피드백 생성 기능을 사용하려면 OPENAI_API_KEY가 설정되어 있어야 합니다."
        )
    from app.infrastructure.feedback.openai_generator import OpenAiFeedbackGenerator

    return OpenAiFeedbackGenerator(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        timeout_seconds=settings.feedback_generator_timeout_seconds,
    )
