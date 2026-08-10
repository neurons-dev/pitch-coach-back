from __future__ import annotations

from app.domain.entities import (
    MetricCalculationInput,
    MetricScoreInput,
    StructureAnalysisResult,
    TranscriptSegmentFeatures,
    TranscriptWordFeatures,
)
from app.domain.filler import (
    find_filler_candidates,
    occurrence_from_candidate,
)
from app.domain.filler_detector import FillerDetectionResult
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


def _word(
    start_ms: int,
    end_ms: int,
    text: str,
    probability: float = 0.9,
) -> TranscriptWordFeatures:
    return TranscriptWordFeatures(
        start_ms=start_ms,
        end_ms=end_ms,
        text=text,
        probability=probability,
    )


def _segment(
    start_ms: int,
    end_ms: int,
    text: str = "",
    avg_logprob: float = -0.1,
    words: list[TranscriptWordFeatures] | None = None,
) -> TranscriptSegmentFeatures:
    return TranscriptSegmentFeatures(
        start_ms=start_ms,
        end_ms=end_ms,
        text=text,
        avg_logprob=avg_logprob,
        words=words or [],
    )


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


def _detection_for_words(calc_input: MetricCalculationInput, words: set[str]) -> FillerDetectionResult:
    occurrences = [
        occurrence_from_candidate(candidate, reason="LLM_JUDGED", evidence="테스트용 판단 근거")
        for candidate in find_filler_candidates(calc_input)
        if candidate.text in words
    ]
    return FillerDetectionResult(occurrences=occurrences, detector="openai")


class TestCalcFiller:
    def test_no_filler_words_scores_100(self):
        calc_input = _calc_input("안녕하세요 오늘은 발표를 시작하겠습니다", duration_ms=10_000)
        result = calc_filler(calc_input, _detection_for_words(calc_input, set()))
        assert result.score == 100
        assert result.raw_value == 0.0

    def test_many_filler_words_clamped_to_zero(self):
        calc_input = _calc_input(" ".join(["음"] * 50), duration_ms=10_000)
        result = calc_filler(calc_input, _detection_for_words(calc_input, {"음"}))
        assert result.score == 0

    def test_empty_text_scores_100(self):
        calc_input = _calc_input("", duration_ms=10_000)
        result = calc_filler(calc_input, _detection_for_words(calc_input, set()))
        assert result.score == 100

    def test_zero_duration_short_utterance_is_handled(self):
        # given
        calc_input = _calc_input("음", duration_ms=0)

        # when
        result = calc_filler(calc_input, _detection_for_words(calc_input, {"음"}))

        # then
        assert result.raw_value == 1.0
        assert result.details["perMinute"] == 60.0
        assert result.score == 0

    def test_same_count_scores_better_over_longer_duration(self):
        text = "음 그래서 어 시작하겠습니다"
        short_input = _calc_input(text, duration_ms=10_000)
        long_input = _calc_input(text, duration_ms=300_000)
        short = calc_filler(short_input, _detection_for_words(short_input, {"음", "어"}))
        long = calc_filler(long_input, _detection_for_words(long_input, {"음", "어"}))
        assert long.score > short.score
        assert short.raw_value == long.raw_value == 2.0

    def test_contextual_words_are_plain_candidates(self):
        # given
        text = "그 사람은 그 결과를 발표했습니다. 이제 새로운 기능을 설명하고 약간의 차이를 보겠습니다."
        calc_input = _calc_input(text, duration_ms=10_000)

        # when
        candidates = find_filler_candidates(calc_input)

        # then
        candidate_texts = [item.text for item in candidates]
        assert candidate_texts.count("그") == 2
        assert "이제" in candidate_texts

    def test_candidate_contains_word_timestamp_and_pause(self):
        # given
        text = "이제 시작하겠습니다"
        words = [_word(0, 300, "이제"), _word(900, 1500, "시작하겠습니다")]
        calc_input = _calc_input(
            text,
            duration_ms=1500,
            segments=[_segment(0, 1500, text=text, words=words)],
        )

        # when
        candidates = find_filler_candidates(calc_input)

        # then
        assert candidates[0].text == "이제"
        assert candidates[0].start_ms == 0
        assert candidates[0].end_ms == 300
        assert candidates[0].following_pause_ms == 600

    def test_repeated_and_stuttered_words_are_plain_candidates_left_for_llm_judgment(self):
        # given
        text = "저희 팀은 목표를 목표를 달성했습니다. 발 발표를 시작하겠습니다."
        calc_input = _calc_input(text, duration_ms=5000)

        # when
        candidates = find_filler_candidates(calc_input)
        candidate_texts = [item.text for item in candidates]

        # then
        assert candidate_texts.count("목표를") == 2
        assert "발" in candidate_texts

    def test_repeated_sentences_keep_distinct_candidate_positions(self):
        # given
        text = "음 발표를 시작합니다. 음 발표를 시작합니다."
        calc_input = _calc_input(text, duration_ms=5000)

        # when
        candidates = [c for c in find_filler_candidates(calc_input) if c.text == "음"]

        # then
        assert [(item.text, item.start_char) for item in candidates] == [
            ("음", 0),
            ("음", text.rindex("음")),
        ]

    def test_self_correction_marker_is_a_plain_candidate_left_for_llm_judgment(self):
        # given
        text = "이번 목표는... 아니, 핵심 목표는 이탈률 감소입니다."
        calc_input = _calc_input(text, duration_ms=5000)

        # when
        candidates = find_filler_candidates(calc_input)

        # then
        assert any(item.text == "아니" for item in candidates)

    def test_metric_details_store_count_rate_positions_and_reasons(self):
        # given
        calc_input = _calc_input("약간 어려웠습니다.", duration_ms=30_000)
        candidate = find_filler_candidates(calc_input)[0]
        detection = FillerDetectionResult(
            occurrences=[
                occurrence_from_candidate(
                    candidate,
                    reason="LLM_JUDGED",
                    evidence="정도 표현이 내용에 필요하지 않은 망설임으로 사용됨",
                )
            ],
            detector="openai",
            model="gpt-4o-mini",
            prompt_version="llm-filler-v2",
        )

        # when
        result = calc_filler(calc_input, detection)

        # then
        assert result.raw_value == 1.0
        assert result.details["totalCount"] == 1
        assert result.details["perMinute"] == 2.0
        assert result.details["occurrences"][0] == {
            "text": "약간",
            "startChar": 0,
            "endChar": 2,
            "startMs": None,
            "endMs": None,
            "precedingPauseMs": None,
            "followingPauseMs": None,
            "reason": "LLM_JUDGED",
            "evidence": "정도 표현이 내용에 필요하지 않은 망설임으로 사용됨",
        }
        assert result.details["detector"] == "openai"
        assert result.details["model"] == "gpt-4o-mini"
        assert result.details["promptVersion"] == "llm-filler-v2"


def _structure_analysis(
    *,
    score: int = 80,
    intro: bool = True,
    body: bool = True,
    conclusion: bool = True,
    reasoning: str = "도입, 본론, 결론이 모두 확인됩니다.",
    analyzer: str = "openai",
    intro_evidence: str | None = "안녕하세요",
    body_evidence: str | None = "본론 내용",
    conclusion_evidence: str | None = "마지막으로 정리하면",
    model: str | None = "gpt-4o-mini",
    prompt_version: str | None = "llm-structure-v1",
) -> StructureAnalysisResult:
    return StructureAnalysisResult(
        score=score,
        intro=intro,
        body=body,
        conclusion=conclusion,
        reasoning=reasoning,
        analyzer=analyzer,
        intro_evidence=intro_evidence,
        body_evidence=body_evidence,
        conclusion_evidence=conclusion_evidence,
        model=model,
        prompt_version=prompt_version,
    )


class TestCalcStructure:
    def test_maps_analysis_result_to_metric_score(self):
        # given
        analysis = _structure_analysis(score=85, conclusion=False, conclusion_evidence=None)

        # when
        result = calc_structure(analysis)

        # then
        assert result.metric_code == "STRUCTURE"
        assert result.score == 85
        assert result.details["intro"] is True
        assert result.details["body"] is True
        assert result.details["conclusion"] is False
        assert result.details["conclusionEvidence"] is None
        assert result.details["reasoning"] == analysis.reasoning
        assert result.details["analyzer"] == "openai"
        assert result.details["model"] == "gpt-4o-mini"
        assert result.details["promptVersion"] == "llm-structure-v1"

    def test_score_is_clamped_to_valid_range(self):
        # given
        analysis = _structure_analysis(score=150)

        # when
        result = calc_structure(analysis)

        # then
        assert result.score == 100


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


class TestCalcAllMetrics:
    def test_returns_six_metrics_including_pronunciation(self):
        segments = [_segment(0, 1000), _segment(1000, 2000)]
        calc_input = _calc_input("안녕하세요", 2000, segments)
        pronunciation_metric = MetricScoreInput(metric_code="PRONUNCIATION", score=80)
        metrics = calc_all_metrics(
            calc_input,
            pronunciation_metric,
            structure_analysis=_structure_analysis(),
            filler_detection=_detection_for_words(calc_input, set()),
        )
        codes = {m.metric_code for m in metrics}
        assert codes == {"SPEED", "FILLER", "STRUCTURE", "DELIVERY", "PRONUNCIATION", "FLUENCY"}

    def test_fluency_override_replaces_local_fluency_metric(self):
        segments = [_segment(0, 1000), _segment(1000, 2000)]
        calc_input = _calc_input("안녕하세요", 2000, segments)
        pronunciation_metric = MetricScoreInput(metric_code="PRONUNCIATION", score=80)
        fluency_override = MetricScoreInput(metric_code="FLUENCY", score=99, details={"provider": "azure"})
        metrics = calc_all_metrics(
            calc_input,
            pronunciation_metric,
            structure_analysis=_structure_analysis(),
            filler_detection=_detection_for_words(calc_input, set()),
            fluency_override=fluency_override,
        )
        fluency = next(m for m in metrics if m.metric_code == "FLUENCY")
        assert fluency.score == 99
        assert fluency.details == {"provider": "azure"}


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
