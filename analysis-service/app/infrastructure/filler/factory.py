from __future__ import annotations

from app.core.config import Settings
from app.domain.filler_detector import FillerDetector
from app.infrastructure.filler.conservative_detector import ConservativeFillerDetector


def create_filler_detector(settings: Settings) -> FillerDetector:
    provider = settings.filler_detector.lower()
    conservative = ConservativeFillerDetector()

    if provider == "conservative":
        return conservative

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError(
                "FILLER_DETECTOR=openai 인데 OPENAI_API_KEY가 설정되지 않았습니다."
            )
        from app.infrastructure.filler.fallback_detector import FallbackFillerDetector
        from app.infrastructure.filler.openai_detector import OpenAiFillerDetector

        primary = OpenAiFillerDetector(
            api_key=settings.openai_api_key,
            model=settings.filler_detector_model,
            timeout_seconds=settings.filler_detector_timeout_seconds,
        )
        return FallbackFillerDetector(primary=primary, fallback=conservative)

    raise ValueError(
        f"알 수 없는 FILLER_DETECTOR: {provider!r} (openai/conservative 중 하나)"
    )
