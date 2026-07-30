from __future__ import annotations

from app.core.config import Settings
from app.domain.pronunciation import PronunciationAssessor
from app.infrastructure.pronunciation.fallback import FallbackPronunciationAssessor
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
        from app.infrastructure.pronunciation.azure import AzurePronunciationAssessor

        primary = AzurePronunciationAssessor(
            subscription_key=settings.azure_speech_key,
            region=settings.azure_speech_region,
            timeout_seconds=settings.pronunciation_provider_timeout_seconds,
        )
        return FallbackPronunciationAssessor(primary=primary, fallback=local)

    if provider == "clova":
        if not settings.clova_invoke_url or not settings.clova_secret_key:
            raise ValueError(
                "PRONUNCIATION_PROVIDER=clova 인데 CLOVA_INVOKE_URL/CLOVA_SECRET_KEY가 "
                "설정되지 않았습니다."
            )
        from app.infrastructure.pronunciation.clova import ClovaPronunciationAssessor

        primary = ClovaPronunciationAssessor(
            invoke_url=settings.clova_invoke_url,
            secret_key=settings.clova_secret_key,
            timeout_seconds=settings.pronunciation_provider_timeout_seconds,
            max_chunk_seconds=settings.clova_max_chunk_seconds,
        )
        return FallbackPronunciationAssessor(primary=primary, fallback=local)

    raise ValueError(f"알 수 없는 PRONUNCIATION_PROVIDER: {provider!r} (local/azure/clova 중 하나)")
