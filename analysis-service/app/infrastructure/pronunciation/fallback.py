from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from app.domain.entities import MetricCalculationInput, PronunciationAssessment
from app.domain.pronunciation import PronunciationAssessor

logger = logging.getLogger(__name__)


class FallbackPronunciationAssessor:
    def __init__(self, *, primary: PronunciationAssessor, fallback: PronunciationAssessor) -> None:
        self._primary = primary
        self._fallback = fallback

    def assess(
        self, *, audio_path: Path, calc_input: MetricCalculationInput, language: str
    ) -> PronunciationAssessment:
        try:
            return self._primary.assess(audio_path=audio_path, calc_input=calc_input, language=language)
        except Exception as exc:
            logger.warning(
                "pronunciation provider failed, falling back to local: %s", type(exc).__name__
            )
            result = self._fallback.assess(audio_path=audio_path, calc_input=calc_input, language=language)
            return replace(result, fallback_reason=type(exc).__name__)
