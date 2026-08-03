from __future__ import annotations

from app.core.config import Settings
from app.domain.pronunciation import PronunciationAssessor
from app.infrastructure.pronunciation.local import LocalPronunciationAssessor


def create_pronunciation_assessor(settings: Settings) -> PronunciationAssessor:
    provider = settings.pronunciation_provider.lower()

    if provider == "local":
        return LocalPronunciationAssessor()

    raise ValueError(f"알 수 없는 PRONUNCIATION_PROVIDER: {provider!r} (local만 지원)")
