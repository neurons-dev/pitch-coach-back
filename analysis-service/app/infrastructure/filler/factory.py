from __future__ import annotations

from app.core.config import Settings
from app.domain.filler_detector import FillerDetector


def create_filler_detector(settings: Settings) -> FillerDetector:
    if not settings.openai_api_key:
        raise ValueError(
            "필러 탐지 기능을 사용하려면 OPENAI_API_KEY가 설정되어 있어야 합니다."
        )
    from app.infrastructure.filler.openai_detector import OpenAiFillerDetector

    return OpenAiFillerDetector(
        api_key=settings.openai_api_key,
        model=settings.filler_detector_model,
        timeout_seconds=settings.filler_detector_timeout_seconds,
    )
