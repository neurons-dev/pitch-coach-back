from __future__ import annotations

from app.core.config import Settings
from app.domain.structure_analyzer import StructureAnalyzer


def create_structure_analyzer(settings: Settings) -> StructureAnalyzer:
    if not settings.openai_api_key:
        raise ValueError(
            "구조 분석 기능을 사용하려면 OPENAI_API_KEY가 설정되어 있어야 합니다."
        )
    from app.infrastructure.structure.openai_analyzer import OpenAiStructureAnalyzer

    return OpenAiStructureAnalyzer(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        timeout_seconds=settings.structure_analyzer_timeout_seconds,
    )
