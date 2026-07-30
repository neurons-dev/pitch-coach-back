from __future__ import annotations

from app.domain.entities import MetricCalculationInput, MetricScoreInput, TranscriptSegmentFeatures
from app.domain.feedback import build_coach_comment, build_feedback_items
from app.domain.metrics import (
    calc_all_metrics,
    calc_delivery,
    calc_filler,
    calc_fluency,
    calc_overall_score,
    calc_speech_silence_ms,
    calc_speed,
    calc_structure,
)
from app.infrastructure.pronunciation.local import LocalPronunciationAssessor


def _segment(start_ms: int, end_ms: int, text: str = "", avg_logprob: float = -0.1) -> TranscriptSegmentFeatures:
    return TranscriptSegmentFeatures(start_ms=start_ms, end_ms=end_ms, text=text, avg_logprob=avg_logprob)


def _calc_input(text: str, duration_ms: int, segments: list[TranscriptSegmentFeatures] | None = None) -> MetricCalculationInput:
    return MetricCalculationInput(text=text, duration_ms=duration_ms, segments=segments or [])


class TestCalcSpeed:
    def test_within_target_range_scores_high(self):
        result = calc_speed(_calc_input("가" * 375, duration_ms=60_000))
        assert result.metric_code == "SPEED"
        assert result.score == 95
        assert result.unit == "CPM"

    def test_exactly_at_lower_boundary_scores_high(self):
        result = calc_speed(_calc_input("가" * 300, duration_ms=60_000))
        assert result.score == 95

    def test_too_fast_penalized_but_clamped(self):
        result = calc_speed(_calc_input("가" * 5000, duration_ms=60_000))
        assert 0 <= result.score <= 100
        assert result.score < 95

    def test_zero_duration_does_not_crash(self):
        result = calc_speed(_calc_input("안녕하세요", duration_ms=0))
        assert 0 <= result.score <= 100


class TestCalcFiller:
    def test_no_filler_words_scores_100(self):
        result = calc_filler(_calc_input("안녕하세요 오늘은 발표를 시작하겠습니다", duration_ms=10_000))
        assert result.score == 100
        assert result.raw_value == 0.0

    def test_counts_only_whole_word_matches(self):
        result = calc_filler(_calc_input("그래서 그림을 그렸어요", duration_ms=10_000))
        assert result.raw_value == 0.0

    def test_many_filler_words_clamped_to_zero(self):
        result = calc_filler(_calc_input(" ".join(["음"] * 50), duration_ms=10_000))
        assert result.score == 0

    def test_empty_text_scores_100(self):
        result = calc_filler(_calc_input("", duration_ms=10_000))
        assert result.score == 100


class TestCalcStructure:
    def test_all_markers_present_scores_100(self):
        text = "안녕하세요 오늘은 그리고 예를 들어 마지막으로 정리하면"
        result = calc_structure(_calc_input(text, duration_ms=10_000))
        assert result.score == 100

    def test_no_markers_scores_40(self):
        result = calc_structure(_calc_input("발표 내용입니다", duration_ms=10_000))
        assert result.score == 40

    def test_empty_text_scores_40(self):
        result = calc_structure(_calc_input("", duration_ms=10_000))
        assert result.score == 40


class TestCalcDelivery:
    def test_uniform_segment_lengths_scores_100(self):
        segments = [_segment(i * 1000, i * 1000 + 1000) for i in range(5)]
        result = calc_delivery(_calc_input("text", 5000, segments))
        assert result.score == 100

    def test_fewer_than_two_segments_scores_default_70(self):
        result = calc_delivery(_calc_input("text", 1000, [_segment(0, 1000)]))
        assert result.score == 70

    def test_no_segments_scores_default_70(self):
        result = calc_delivery(_calc_input("text", 1000, []))
        assert result.score == 70

    def test_highly_irregular_lengths_penalized(self):
        segments = [_segment(0, 100), _segment(100, 5000)]
        result = calc_delivery(_calc_input("text", 5000, segments))
        assert result.score < 100


class TestCalcFluency:
    def test_continuous_speech_scores_high(self):
        segments = [_segment(0, 5000)]
        result = calc_fluency(_calc_input("text", 5000, segments))
        assert result.score == 100
        assert result.details["longPauseCount"] == 0

    def test_zero_duration_scores_default_70(self):
        result = calc_fluency(_calc_input("text", 0, [_segment(0, 0)]))
        assert result.score == 70

    def test_no_segments_scores_default_70(self):
        result = calc_fluency(_calc_input("text", 5000, []))
        assert result.score == 70

    def test_long_pause_between_segments_penalized_and_counted(self):
        segments = [_segment(0, 1000), _segment(4000, 5000)]
        result = calc_fluency(_calc_input("text", 5000, segments))
        assert result.details["longPauseCount"] == 1
        assert result.score < 100

    def test_mostly_silent_single_segment_floors_around_thirty(self):
        segments = [_segment(0, 100)]
        result = calc_fluency(_calc_input("text", 1_000_000, segments))
        assert result.score == 30

    def test_many_long_pauses_clamped_to_zero(self):
        segments = [_segment(i * 3010, i * 3010 + 10) for i in range(20)]
        result = calc_fluency(_calc_input("text", segments[-1].end_ms, segments))
        assert result.score == 0
        assert result.details["longPauseCount"] == 19


class TestLocalPronunciationAssessor:
    def test_high_confidence_segments_score_high(self):
        segments = [_segment(0, 1000, avg_logprob=-0.05), _segment(1000, 2000, avg_logprob=-0.02)]
        result = LocalPronunciationAssessor().assess(_calc_input("text", 2000, segments))
        assert result.metric_code == "PRONUNCIATION"
        assert result.score > 90
        assert result.details == {"provider": "local"}

    def test_low_confidence_segments_score_low(self):
        segments = [_segment(0, 1000, avg_logprob=-0.9)]
        result = LocalPronunciationAssessor().assess(_calc_input("text", 1000, segments))
        assert result.score < 20

    def test_no_segments_scores_default_70(self):
        result = LocalPronunciationAssessor().assess(_calc_input("text", 1000, []))
        assert result.score == 70

    def test_extreme_logprob_clamped_within_0_100(self):
        segments = [_segment(0, 1000, avg_logprob=-5.0)]
        result = LocalPronunciationAssessor().assess(_calc_input("text", 1000, segments))
        assert 0 <= result.score <= 100


class TestCalcAllMetrics:
    def test_returns_six_metrics_including_pronunciation(self):
        segments = [_segment(0, 1000), _segment(1000, 2000)]
        metrics = calc_all_metrics(_calc_input("안녕하세요", 2000, segments), LocalPronunciationAssessor())
        codes = {m.metric_code for m in metrics}
        assert codes == {"SPEED", "FILLER", "STRUCTURE", "DELIVERY", "PRONUNCIATION", "FLUENCY"}


class TestCalcOverallScore:
    def test_averages_metric_scores(self):
        metrics = [
            MetricScoreInput(metric_code="SPEED", score=80),
            MetricScoreInput(metric_code="FILLER", score=100),
        ]
        assert calc_overall_score(metrics) == 90

    def test_empty_metrics_scores_zero(self):
        assert calc_overall_score([]) == 0


class TestCalcSpeechSilenceMs:
    def test_computes_speech_and_silence(self):
        segments = [_segment(0, 1000), _segment(2000, 3000)]
        speech_ms, silence_ms = calc_speech_silence_ms(_calc_input("text", 4000, segments))
        assert speech_ms == 2000
        assert silence_ms == 2000

    def test_speech_exceeding_duration_clamps_silence_to_zero(self):
        segments = [_segment(0, 10_000)]
        speech_ms, silence_ms = calc_speech_silence_ms(_calc_input("text", 1000, segments))
        assert silence_ms == 0


class TestBuildCoachComment:
    def test_high_score_uses_positive_base(self):
        metrics = [MetricScoreInput(metric_code="SPEED", score=90)]
        comment = build_coach_comment(90, metrics)
        assert comment.startswith("전반적으로 안정적인 발표였어요")

    def test_low_score_appends_weakest_metric_hint(self):
        metrics = [
            MetricScoreInput(metric_code="SPEED", score=95),
            MetricScoreInput(metric_code="FILLER", score=40),
        ]
        comment = build_coach_comment(60, metrics)
        assert "필러 단어" in comment

    def test_empty_metrics_does_not_crash(self):
        comment = build_coach_comment(50, [])
        assert isinstance(comment, str)


class TestBuildFeedbackItems:
    def test_summary_item_always_first(self):
        items = build_feedback_items(80, "총평입니다", [])
        assert items[0].item_type == "summary"
        assert items[0].description == "총평입니다"

    def test_low_score_metric_produces_improvement_item(self):
        metrics = [MetricScoreInput(metric_code="SPEED", score=50)]
        items = build_feedback_items(50, "총평", metrics)
        improvement_items = [i for i in items if i.item_type == "improvement"]
        assert len(improvement_items) == 1
        assert improvement_items[0].metric_code == "SPEED"

    def test_high_score_metric_produces_strength_item(self):
        metrics = [MetricScoreInput(metric_code="SPEED", score=90)]
        items = build_feedback_items(90, "총평", metrics)
        strength_items = [i for i in items if i.item_type == "strength"]
        assert len(strength_items) == 1

    def test_mid_range_score_produces_no_extra_item(self):
        metrics = [MetricScoreInput(metric_code="SPEED", score=75)]
        items = build_feedback_items(75, "총평", metrics)
        assert len(items) == 1
