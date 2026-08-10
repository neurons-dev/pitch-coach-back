from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.entities import MetricCalculationInput

HIGH_CONFIDENCE_FILLERS = frozenset({"어", "음", "뭐랄까"})


@dataclass(frozen=True)
class FillerCandidate:
    text: str
    start_char: int
    end_char: int
    candidate_type: str
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


def _standalone_pattern(word: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![가-힣]){re.escape(word)}(?![가-힣])")


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
    candidate_type: str,
    timed_words: list[_TimedTextSpan],
) -> FillerCandidate:
    start_ms, end_ms, preceding_pause_ms, following_pause_ms = _timing_for_span(
        timed_words, start_char, end_char
    )
    return FillerCandidate(
        text=text,
        start_char=start_char,
        end_char=end_char,
        candidate_type=candidate_type,
        start_ms=start_ms,
        end_ms=end_ms,
        preceding_pause_ms=preceding_pause_ms,
        following_pause_ms=following_pause_ms,
    )


def find_filler_candidates(calc_input: MetricCalculationInput) -> list[FillerCandidate]:
    timed_words = _locate_timed_words(calc_input)
    candidates: dict[tuple[int, int], FillerCandidate] = {}

    repeated_pattern = re.compile(
        r"(?<![가-힣])(?P<first>[가-힣]{1,})\s+(?P<second>(?P=first))(?![가-힣])"
    )
    for match in repeated_pattern.finditer(calc_input.text):
        item = _candidate(
            text=match.group("second"),
            start_char=match.start("second"),
            end_char=match.end("second"),
            candidate_type="REPETITION",
            timed_words=timed_words,
        )
        candidates.setdefault((item.start_char, item.end_char), item)

    stutter_pattern = re.compile(
        r"(?<![가-힣])(?P<fragment>[가-힣]{1,2})\s+(?P<word>[가-힣]{2,})(?![가-힣])"
    )
    for match in stutter_pattern.finditer(calc_input.text):
        fragment = match.group("fragment")
        if not match.group("word").startswith(fragment):
            continue
        item = _candidate(
            text=fragment,
            start_char=match.start("fragment"),
            end_char=match.end("fragment"),
            candidate_type="STUTTER",
            timed_words=timed_words,
        )
        candidates.setdefault((item.start_char, item.end_char), item)

    word_pattern = re.compile(r"[가-힣]+")
    for match in word_pattern.finditer(calc_input.text):
        item = _candidate(
            text=match.group(),
            start_char=match.start(),
            end_char=match.end(),
            candidate_type="LEXICAL",
            timed_words=timed_words,
        )
        candidates.setdefault((item.start_char, item.end_char), item)

    return sorted(candidates.values(), key=lambda item: (item.start_char, item.end_char))


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


def detect_conservative_filler_occurrences(
    calc_input: MetricCalculationInput,
) -> list[FillerOccurrence]:
    timed_words = _locate_timed_words(calc_input)
    occurrences = [
        occurrence_from_candidate(
            _candidate(
                text=match.group(),
                start_char=match.start(),
                end_char=match.end(),
                candidate_type="LEXICAL",
                timed_words=timed_words,
            ),
            reason="HIGH_CONFIDENCE_MARKER",
            evidence="LLM 장애 시 사용하는 보수적 필러 표지",
        )
        for word in HIGH_CONFIDENCE_FILLERS
        for match in _standalone_pattern(word).finditer(calc_input.text)
    ]
    return sorted(occurrences, key=lambda item: item.start_char)


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
