from __future__ import annotations

from typing import Protocol

from app.domain.entities import MetricCalculationInput, MetricScoreInput


class PronunciationAssessor(Protocol):
    def assess(self, calc_input: MetricCalculationInput) -> MetricScoreInput: ...
