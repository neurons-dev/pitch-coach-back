from __future__ import annotations

from app.domain.entities import MetricCalculationInput
from app.domain.filler import detect_conservative_filler_occurrences
from app.domain.filler_detector import FillerDetectionResult


class ConservativeFillerDetector:
    def detect(self, calc_input: MetricCalculationInput) -> FillerDetectionResult:
        return FillerDetectionResult(
            occurrences=detect_conservative_filler_occurrences(calc_input),
            detector="conservative-v1",
        )
