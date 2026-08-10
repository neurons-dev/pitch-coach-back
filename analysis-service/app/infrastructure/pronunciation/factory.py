from __future__ import annotations

from app.core.config import Settings
from app.domain.pronunciation import PronunciationAssessor
from app.infrastructure.pronunciation.local import LocalPronunciationAssessor


def create_pronunciation_assessor(settings: Settings) -> PronunciationAssessor:
    provider = settings.pronunciation_provider.lower()
    local = LocalPronunciationAssessor()

    if provider == "local":
        return local

    if provider == "azure":
        if not settings.azure_speech_key:
            raise ValueError(
                "PRONUNCIATION_PROVIDER=azure 인데 AZURE_SPEECH_KEY가 설정되지 않았습니다."
            )
        from app.infrastructure.pronunciation.azure_speech_sdk import (
            AzureSpeechSdkPronunciationAssessor,
        )
        from app.infrastructure.pronunciation.fallback import FallbackPronunciationAssessor

        primary = AzureSpeechSdkPronunciationAssessor(
            subscription_key=settings.azure_speech_key,
            region=settings.azure_speech_region,
            timeout_seconds=settings.pronunciation_provider_timeout_seconds,
        )
        return FallbackPronunciationAssessor(primary=primary, fallback=local)

    raise ValueError(f"알 수 없는 PRONUNCIATION_PROVIDER: {provider!r} (local/azure 중 하나)")
