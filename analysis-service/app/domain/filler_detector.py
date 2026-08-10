from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.domain.entities import MetricCalculationInput
from app.domain.filler import FillerOccurrence


@dataclass(frozen=True)
class FillerDetectionResult:
    detector: str
    occurrences: list[FillerOccurrence] = field(default_factory=list)
    model: str | None = None
    prompt_version: str | None = None


class FillerDetector(Protocol):
    def detect(self, calc_input: MetricCalculationInput) -> FillerDetectionResult: ...
