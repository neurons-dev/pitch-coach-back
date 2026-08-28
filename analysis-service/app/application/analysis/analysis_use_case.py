from __future__ import annotations

import logging
from collections.abc import Callable

from app.domain.audio import AudioNormalizer, AudioStorage, SpeechTranscriber
from app.domain.entities import (
    AnalysisResultInput,
    MetricCalculationInput,
    MetricScoreInput,
    TranscriptSegmentFeatures,
    TranscriptWordFeatures,
)
from app.domain.feedback_generator import FeedbackGenerator
from app.domain.filler_detector import FillerDetector
from app.domain.metrics import (
    SCORING_RULE_VERSION,
    calc_all_metrics,
    calc_overall_score,
    calc_speech_silence_ms,
)
from app.domain.pronunciation import PronunciationAssessor
from app.domain.structure_analyzer import StructureAnalyzer

logger = logging.getLogger(__name__)

_DEFAULT_LANGUAGE = "ko-KR"

ProgressReporter = Callable[[str, int], None]

# 분석은 한 잡 안에서 수 분이 걸리므로 단계마다 진행률을 올려 준다.
# 진행률이 20%에 멈춰 있으면 호출자가 정상 진행과 멈춤을 구분할 수 없다.
_STAGE_TRANSCRIBING = ("TRANSCRIBING", 35)
_STAGE_ASSESSING_PRONUNCIATION = ("ASSESSING_PRONUNCIATION", 50)
_STAGE_ANALYZING_CONTENT = ("ANALYZING_CONTENT", 65)
_STAGE_GENERATING_FEEDBACK = ("GENERATING_FEEDBACK", 85)


class AnalysisUseCase:
    def __init__(
        self,
        *,
        audio_storage: AudioStorage,
        audio_normalizer: AudioNormalizer,
        speech_transcriber: SpeechTranscriber,
        pronunciation_assessor: PronunciationAssessor,
        feedback_generator: FeedbackGenerator,
        filler_detector: FillerDetector,
        structure_analyzer: StructureAnalyzer,
        pipeline_version: str,
        language: str = _DEFAULT_LANGUAGE,
    ) -> None:
        self._audio_storage = audio_storage
        self._audio_normalizer = audio_normalizer
        self._speech_transcriber = speech_transcriber
        self._pronunciation_assessor = pronunciation_assessor
        self._feedback_generator = feedback_generator
        self._filler_detector = filler_detector
        self._structure_analyzer = structure_analyzer
        self._pipeline_version = pipeline_version
        self._language = language

    def run(
        self,
        *,
        audio_object_key: str,
        analysis_version: str,
        presentation_title: str | None = None,
        practice_type_code: str | None = None,
        target_duration_sec: int | None = None,
        progress_reporter: ProgressReporter | None = None,
    ) -> AnalysisResultInput:
        downloaded = self._audio_storage.download(audio_object_key)
        source_duration_ms = downloaded.duration_ms
        try:
            normalized_path = self._audio_normalizer.normalize(downloaded.path)
        finally:
            downloaded.path.unlink(missing_ok=True)

        self._report(progress_reporter, _STAGE_TRANSCRIBING)

        try:
            transcript = self._speech_transcriber.transcribe(
                normalized_path, language=self._language, duration_ms=source_duration_ms
            )
            calc_input = MetricCalculationInput(
                text=transcript.text,
                duration_ms=transcript.duration_ms,
                segments=[
                    TranscriptSegmentFeatures(
                        start_ms=segment.start_ms,
                        end_ms=segment.end_ms,
                        text=segment.text,
                        avg_logprob=segment.avg_logprob,
                        words=[
                            TranscriptWordFeatures(
                                start_ms=word.start_ms,
                                end_ms=word.end_ms,
                                text=word.text,
                                probability=word.probability,
                            )
                            for word in segment.words
                        ],
                    )
                    for segment in transcript.segments
                ],
            )
            self._report(progress_reporter, _STAGE_ASSESSING_PRONUNCIATION)
            assessment = self._pronunciation_assessor.assess(
                audio_path=normalized_path, calc_input=calc_input, language=self._language
            )
        finally:
            normalized_path.unlink(missing_ok=True)

        pronunciation_details = {"provider": assessment.provider}
        pronunciation_metric = MetricScoreInput(
            metric_code="PRONUNCIATION",
            score=assessment.pronunciation_score,
            raw_value=(
                float(assessment.accuracy_score) if assessment.accuracy_score is not None else None
            ),
            unit="ACCURACY" if assessment.accuracy_score is not None else None,
            details=pronunciation_details,
        )
        fluency_override = None
        if assessment.fluency_score is not None:
            fluency_override = MetricScoreInput(
                metric_code="FLUENCY",
                score=assessment.fluency_score,
                details=pronunciation_details,
            )

        self._report(progress_reporter, _STAGE_ANALYZING_CONTENT)
        filler_detection = self._filler_detector.detect(calc_input)
        structure_result = self._structure_analyzer.analyze(
            calc_input,
            practice_type_code=practice_type_code,
            target_duration_sec=target_duration_sec,
        )
        metrics = calc_all_metrics(
            calc_input,
            pronunciation_metric,
            structure_analysis=structure_result,
            filler_detection=filler_detection,
            fluency_override=fluency_override,
        )
        overall_score = calc_overall_score(metrics)
        total_speech_ms, total_silence_ms = calc_speech_silence_ms(calc_input)
        self._report(progress_reporter, _STAGE_GENERATING_FEEDBACK)
        feedback_result = self._feedback_generator.generate(
            transcript_text=transcript.text,
            metrics=metrics,
            overall_score=overall_score,
            presentation_title=presentation_title,
            practice_type_code=practice_type_code,
        )

        return AnalysisResultInput(
            overall_score=overall_score,
            pipeline_version=self._pipeline_version,
            stt_model_version=transcript.model_version,
            scoring_rule_version=SCORING_RULE_VERSION,
            coach_comment=feedback_result.coach_comment,
            transcript_text=transcript.text,
            transcript_segments=[
                {"startMs": segment.start_ms, "endMs": segment.end_ms, "text": segment.text}
                for segment in transcript.segments
            ],
            total_speech_ms=total_speech_ms,
            total_silence_ms=total_silence_ms,
            model_info={
                "language": transcript.language,
                "pronunciationProvider": assessment.provider,
                "feedbackGenerator": feedback_result.generator,
                "feedbackModel": feedback_result.model,
                "feedbackPromptVersion": feedback_result.prompt_version,
                "fillerDetector": filler_detection.detector,
                "fillerModel": filler_detection.model,
                "fillerPromptVersion": filler_detection.prompt_version,
                "structureAnalyzer": structure_result.analyzer,
                "structureModel": structure_result.model,
                "structurePromptVersion": structure_result.prompt_version,
            },
            metric_scores=metrics,
            feedback_items=feedback_result.feedback_items,
        )

    @staticmethod
    def _report(reporter: ProgressReporter | None, stage: tuple[str, int]) -> None:
        # 진행률 보고는 부가 정보이므로 실패해도 분석 자체를 중단시키지 않는다.
        if reporter is None:
            return
        try:
            reporter(*stage)
        except Exception:
            logger.warning("진행률 보고 실패 stage=%s", stage[0], exc_info=True)
