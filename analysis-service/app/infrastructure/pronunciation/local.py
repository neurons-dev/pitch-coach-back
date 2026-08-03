from __future__ import annotations

from pathlib import Path

from app.domain.entities import MetricCalculationInput, PronunciationAssessment


class LocalPronunciationAssessor:
    def assess(
        self, *, audio_path: Path, calc_input: MetricCalculationInput, language: str
    ) -> PronunciationAssessment:
        if not calc_input.segments:
            return PronunciationAssessment(provider="local", pronunciation_score=70)

        avg_logprob = sum(s.avg_logprob for s in calc_input.segments) / len(calc_input.segments)
        score = int(max(0, min(100, round((avg_logprob + 1.0) * 100))))

        return PronunciationAssessment(
            provider="local",
            pronunciation_score=score,
            raw_response={"avgLogprob": round(avg_logprob, 3)},
        )
