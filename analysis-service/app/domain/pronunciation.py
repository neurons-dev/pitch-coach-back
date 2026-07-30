from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.domain.entities import MetricCalculationInput, PronunciationAssessment


class PronunciationAssessor(Protocol):
    def assess(
        self, *, audio_path: Path, calc_input: MetricCalculationInput, language: str
    ) -> PronunciationAssessment: ...
