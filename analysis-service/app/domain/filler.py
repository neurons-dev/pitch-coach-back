from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.entities import MetricCalculationInput

_WORD_PATTERN = re.compile(r"[가-힣]+")


@dataclass(frozen=True)
class FillerCandidate:
    text: str
    start_char: int
    end_char: int
    start_ms: int | None = None
    end_ms: int | None = None
    preceding_pause_ms: int | None = None
    following_pause_ms: int | None = None


@dataclass(frozen=True)
class FillerOccurrence:
    text: str
    start_char: int
    end_char: int
    reason: str
    evidence: str
    start_ms: int | None = None
    end_ms: int | None = None
    preceding_pause_ms: int | None = None
    following_pause_ms: int | None = None


@dataclass(frozen=True)
class _TimedTextSpan:
    start_char: int
    end_char: int
    start_ms: int
    end_ms: int


def _locate_timed_words(calc_input: MetricCalculationInput) -> list[_TimedTextSpan]:
    spans: list[_TimedTextSpan] = []
    cursor = 0
    for segment in calc_input.segments:
        for word in segment.words:
            surface = word.text.strip()
            if not surface:
                continue
            start_char = calc_input.text.find(surface, cursor)
            matched_surface = surface
            if start_char < 0:
                matched_surface = surface.strip(".,!?…:;，。！？：；\"'()[]{}")
                start_char = calc_input.text.find(matched_surface, cursor)
            if start_char < 0 or not matched_surface:
                continue
            end_char = start_char + len(matched_surface)
            spans.append(
                _TimedTextSpan(
                    start_char=start_char,
                    end_char=end_char,
                    start_ms=word.start_ms,
                    end_ms=word.end_ms,
                )
            )
            cursor = end_char
    return spans


def _timing_for_span(
    timed_words: list[_TimedTextSpan], start_char: int, end_char: int
) -> tuple[int | None, int | None, int | None, int | None]:
    for index, word in enumerate(timed_words):
        if word.start_char < end_char and start_char < word.end_char:
            preceding_pause_ms = (
                max(word.start_ms - timed_words[index - 1].end_ms, 0)
                if index > 0
                else word.start_ms
            )
            following_pause_ms = (
                max(timed_words[index + 1].start_ms - word.end_ms, 0)
                if index + 1 < len(timed_words)
                else None
            )
            return (
                word.start_ms,
                word.end_ms,
                preceding_pause_ms,
                following_pause_ms,
            )
    return None, None, None, None


def _candidate(
    *,
    text: str,
    start_char: int,
    end_char: int,
    timed_words: list[_TimedTextSpan],
) -> FillerCandidate:
    start_ms, end_ms, preceding_pause_ms, following_pause_ms = _timing_for_span(
        timed_words, start_char, end_char
    )
    return FillerCandidate(
        text=text,
        start_char=start_char,
        end_char=end_char,
        start_ms=start_ms,
        end_ms=end_ms,
        preceding_pause_ms=preceding_pause_ms,
        following_pause_ms=following_pause_ms,
    )


def find_filler_candidates(calc_input: MetricCalculationInput) -> list[FillerCandidate]:
    timed_words = _locate_timed_words(calc_input)
    return [
        _candidate(
            text=match.group(),
            start_char=match.start(),
            end_char=match.end(),
            timed_words=timed_words,
        )
        for match in _WORD_PATTERN.finditer(calc_input.text)
    ]


def occurrence_from_candidate(
    candidate: FillerCandidate,
    *,
    reason: str,
    evidence: str,
) -> FillerOccurrence:
    return FillerOccurrence(
        text=candidate.text,
        start_char=candidate.start_char,
        end_char=candidate.end_char,
        reason=reason,
        evidence=evidence,
        start_ms=candidate.start_ms,
        end_ms=candidate.end_ms,
        preceding_pause_ms=candidate.preceding_pause_ms,
        following_pause_ms=candidate.following_pause_ms,
    )


def filler_occurrence_details(occurrence: FillerOccurrence) -> dict:
    return {
        "text": occurrence.text,
        "startChar": occurrence.start_char,
        "endChar": occurrence.end_char,
        "startMs": occurrence.start_ms,
        "endMs": occurrence.end_ms,
        "precedingPauseMs": occurrence.preceding_pause_ms,
        "followingPauseMs": occurrence.following_pause_ms,
        "reason": occurrence.reason,
        "evidence": occurrence.evidence,
    }
