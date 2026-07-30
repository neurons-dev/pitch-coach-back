from __future__ import annotations

from app.domain.entities import MetricCalculationInput, MetricScoreInput


class LocalPronunciationAssessor:
    def assess(self, calc_input: MetricCalculationInput) -> MetricScoreInput:
        if not calc_input.segments:
            return MetricScoreInput(
                metric_code="PRONUNCIATION",
                score=70,
                raw_value=None,
                unit=None,
                details={"provider": "local"},
            )

        avg_logprob = sum(s.avg_logprob for s in calc_input.segments) / len(calc_input.segments)
        score = int(max(0, min(100, round((avg_logprob + 1.0) * 100))))

        return MetricScoreInput(
            metric_code="PRONUNCIATION",
            score=score,
            raw_value=round(avg_logprob, 3),
            unit="LOGPROB",
            details={"provider": "local"},
        )
