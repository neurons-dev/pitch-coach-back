from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.entities import MetricCalculationInput, MetricScoreInput

SCORING_RULE_VERSION = "coach-ko-v1"

_FILLER_WORDS = ("어", "음", "그", "저기", "이제", "약간", "뭐랄까")

_STRUCTURE_MARKERS = {
    "intro": ("안녕하세요", "먼저", "오늘은"),
    "body": ("그리고", "또한", "예를 들어"),
    "conclusion": ("마지막으로", "결론적으로", "정리하면", "이상입니다"),
}

_SPEECH_SPEED_TARGET_CPM = (300, 450)
_LONG_PAUSE_THRESHOLD_MS = 2000
_FILLER_PENALTY_PER_MINUTE = 10


@dataclass(frozen=True)
class FillerOccurrence:
    text: str
    start_char: int
    end_char: int


@dataclass(frozen=True)
class StructureSignals:
    intro: bool
    body: bool
    conclusion: bool


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return int(max(low, min(high, round(value))))


def calc_speed(calc_input: MetricCalculationInput) -> MetricScoreInput:
    duration_min = max(calc_input.duration_ms / 1000 / 60, 1 / 60)
    char_count = len(calc_input.text.replace(" ", ""))
    cpm = char_count / duration_min

    low, high = _SPEECH_SPEED_TARGET_CPM
    if low <= cpm <= high:
        score = 95
    else:
        distance = (low - cpm) if cpm < low else (cpm - high)
        score = _clamp(95 - distance / 5)

    return MetricScoreInput(metric_code="SPEED", score=score, raw_value=round(cpm, 1), unit="CPM")


def detect_filler_occurrences(text: str) -> list[FillerOccurrence]:
    occurrences: list[FillerOccurrence] = []
    for word in _FILLER_WORDS:
        pattern = rf"(?<![가-힣]){re.escape(word)}(?![가-힣])"
        occurrences.extend(
            FillerOccurrence(text=match.group(), start_char=match.start(), end_char=match.end())
            for match in re.finditer(pattern, text)
        )
    return sorted(occurrences, key=lambda occurrence: (occurrence.start_char, occurrence.end_char))


def calc_filler(calc_input: MetricCalculationInput) -> MetricScoreInput:
    count = len(detect_filler_occurrences(calc_input.text))

    duration_min = max(calc_input.duration_ms / 1000 / 60, 1 / 60)
    per_minute = count / duration_min

    score = _clamp(100 - per_minute * _FILLER_PENALTY_PER_MINUTE)
    return MetricScoreInput(
        metric_code="FILLER",
        score=score,
        raw_value=float(count),
        unit="COUNT",
        details={"perMinute": round(per_minute, 2)},
    )


def detect_structure_signals(calc_input: MetricCalculationInput) -> StructureSignals:
    segments = calc_input.segments
    if not segments:
        text = calc_input.text
        return StructureSignals(
            intro=any(marker in text for marker in _STRUCTURE_MARKERS["intro"]),
            body=any(marker in text for marker in _STRUCTURE_MARKERS["body"]),
            conclusion=any(marker in text for marker in _STRUCTURE_MARKERS["conclusion"]),
        )

    total_ms = max(calc_input.duration_ms, 1)
    early_cutoff = total_ms / 3
    late_cutoff = total_ms * 2 / 3

    intro_text = " ".join(s.text for s in segments if s.start_ms < early_cutoff)
    conclusion_text = " ".join(s.text for s in segments if s.start_ms >= late_cutoff)
    body_text = calc_input.text

    return StructureSignals(
        intro=any(marker in intro_text for marker in _STRUCTURE_MARKERS["intro"]),
        body=any(marker in body_text for marker in _STRUCTURE_MARKERS["body"]),
        conclusion=any(marker in conclusion_text for marker in _STRUCTURE_MARKERS["conclusion"]),
    )


def calc_structure(calc_input: MetricCalculationInput) -> MetricScoreInput:
    signals = detect_structure_signals(calc_input)
    hits = sum((signals.intro, signals.body, signals.conclusion))
    return MetricScoreInput(metric_code="STRUCTURE", score=_clamp(40 + hits * 20), raw_value=None, unit=None)


def calc_delivery(calc_input: MetricCalculationInput) -> MetricScoreInput:
    segments = calc_input.segments
    if len(segments) < 2:
        return MetricScoreInput(metric_code="DELIVERY", score=70, raw_value=None, unit=None)

    lengths = [max(s.end_ms - s.start_ms, 1) for s in segments]
    mean_len = sum(lengths) / len(lengths)
    variance = sum((length - mean_len) ** 2 for length in lengths) / len(lengths)
    stddev = variance**0.5
    coefficient = stddev / mean_len if mean_len else 1.0

    score = _clamp(100 - coefficient * 60)
    return MetricScoreInput(metric_code="DELIVERY", score=score, raw_value=None, unit=None)


def calc_fluency(calc_input: MetricCalculationInput) -> MetricScoreInput:
    segments = calc_input.segments
    if calc_input.duration_ms <= 0 or not segments:
        return MetricScoreInput(metric_code="FLUENCY", score=70, raw_value=None, unit=None)

    speech_ms = sum(max(s.end_ms - s.start_ms, 0) for s in segments)
    silence_ratio = max(0.0, 1 - speech_ms / calc_input.duration_ms)

    long_pause_count = 0
    for prev, curr in zip(segments, segments[1:]):
        gap = curr.start_ms - prev.end_ms
        if gap > _LONG_PAUSE_THRESHOLD_MS:
            long_pause_count += 1

    score = _clamp(100 - silence_ratio * 70 - long_pause_count * 5)
    return MetricScoreInput(
        metric_code="FLUENCY",
        score=score,
        raw_value=round(silence_ratio * 100, 1),
        unit="SILENCE_PCT",
        details={"longPauseCount": long_pause_count},
    )


def calc_all_metrics(
    calc_input: MetricCalculationInput,
    pronunciation_metric: MetricScoreInput,
    fluency_override: MetricScoreInput | None = None,
) -> list[MetricScoreInput]:
    return [
        calc_speed(calc_input),
        calc_filler(calc_input),
        calc_structure(calc_input),
        calc_delivery(calc_input),
        pronunciation_metric,
        fluency_override or calc_fluency(calc_input),
    ]


def calc_overall_score(metrics: list[MetricScoreInput]) -> int:
    if not metrics:
        return 0
    return _clamp(sum(m.score for m in metrics) / len(metrics))


def calc_speech_silence_ms(calc_input: MetricCalculationInput) -> tuple[int, int]:
    speech_ms = sum(max(s.end_ms - s.start_ms, 0) for s in calc_input.segments)
    silence_ms = max(calc_input.duration_ms - speech_ms, 0)
    return speech_ms, silence_ms
