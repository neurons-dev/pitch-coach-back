from __future__ import annotations

from app.core.config import Settings
from app.domain.pronunciation import PronunciationAssessor


def create_pronunciation_assessor(settings: Settings) -> PronunciationAssessor:
    if not settings.azure_speech_key:
        raise ValueError(
            "발음 평가 기능을 사용하려면 AZURE_SPEECH_KEY가 설정되어 있어야 합니다."
        )
    from app.infrastructure.pronunciation.azure_speech_sdk import (
        AzureSpeechSdkPronunciationAssessor,
    )

    return AzureSpeechSdkPronunciationAssessor(
        subscription_key=settings.azure_speech_key,
        region=settings.azure_speech_region,
        timeout_seconds=settings.pronunciation_provider_timeout_seconds,
    )
