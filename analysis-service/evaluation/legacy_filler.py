from __future__ import annotations

import re

from app.domain.entities import MetricCalculationInput
from app.domain.filler import FillerOccurrence
from app.domain.filler_detector import FillerDetectionResult

_FILLER_WORDS = ("어", "음", "그", "저기", "이제", "약간", "뭐랄까")


def detect_legacy_filler_occurrences(
    calc_input: MetricCalculationInput,
) -> FillerDetectionResult:
    occurrences: list[FillerOccurrence] = []
    for word in _FILLER_WORDS:
        pattern = re.compile(rf"(?<![가-힣]){re.escape(word)}(?![가-힣])")
        occurrences.extend(
            FillerOccurrence(
                text=match.group(),
                start_char=match.start(),
                end_char=match.end(),
                reason="LEGACY_KEYWORD",
                evidence="고정 필러 단어와 일치",
            )
            for match in pattern.finditer(calc_input.text)
        )
    return FillerDetectionResult(
        occurrences=sorted(
            occurrences, key=lambda item: (item.start_char, item.end_char)
        ),
        detector="legacy-keyword-v1",
    )
