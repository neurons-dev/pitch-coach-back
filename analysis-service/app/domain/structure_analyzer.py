from __future__ import annotations

from typing import Protocol

from app.domain.entities import MetricCalculationInput, StructureAnalysisResult


class StructureAnalyzer(Protocol):
    def analyze(
        self,
        calc_input: MetricCalculationInput,
        *,
        practice_type_code: str | None = None,
        target_duration_sec: int | None = None,
    ) -> StructureAnalysisResult: ...
