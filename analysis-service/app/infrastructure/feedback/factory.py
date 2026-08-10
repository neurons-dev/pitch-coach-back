from __future__ import annotations

from app.core.config import Settings
from app.domain.feedback_generator import FeedbackGenerator
from app.infrastructure.feedback.template_generator import TemplateFeedbackGenerator


def create_feedback_generator(settings: Settings) -> FeedbackGenerator:
    provider = settings.feedback_generator.lower()
    template = TemplateFeedbackGenerator()

    if provider == "template":
        return template

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError(
                "FEEDBACK_GENERATOR=openai 인데 OPENAI_API_KEY가 설정되지 않았습니다."
            )
        from app.infrastructure.feedback.fallback_generator import FallbackFeedbackGenerator
        from app.infrastructure.feedback.openai_generator import OpenAiFeedbackGenerator

        primary = OpenAiFeedbackGenerator(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout_seconds=settings.feedback_generator_timeout_seconds,
        )
        return FallbackFeedbackGenerator(primary=primary, fallback=template)

    raise ValueError(f"알 수 없는 FEEDBACK_GENERATOR: {provider!r} (template/openai 중 하나)")
