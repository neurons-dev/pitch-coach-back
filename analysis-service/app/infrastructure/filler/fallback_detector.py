from __future__ import annotations

import logging
from dataclasses import replace

from app.domain.entities import MetricCalculationInput
from app.domain.errors import AnalysisError
from app.domain.filler_detector import FillerDetectionResult, FillerDetector

logger = logging.getLogger(__name__)


class FallbackFillerDetector:
    def __init__(self, *, primary: FillerDetector, fallback: FillerDetector) -> None:
        self._primary = primary
        self._fallback = fallback

    def detect(self, calc_input: MetricCalculationInput) -> FillerDetectionResult:
        try:
            return self._primary.detect(calc_input)
        except AnalysisError as exc:
            logger.warning(
                "filler detector failed, falling back to rule-based: code=%s", exc.code
            )
            return replace(
                self._fallback.detect(calc_input),
                fallback_reason=exc.code,
            )
