from __future__ import annotations

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

_DEFAULT_LANGUAGE = "ko-KR"


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
        pipeline_version: str,
        language: str = _DEFAULT_LANGUAGE,
    ) -> None:
        self._audio_storage = audio_storage
        self._audio_normalizer = audio_normalizer
        self._speech_transcriber = speech_transcriber
        self._pronunciation_assessor = pronunciation_assessor
        self._feedback_generator = feedback_generator
        self._filler_detector = filler_detector
        self._pipeline_version = pipeline_version
        self._language = language

    def run(
        self,
        *,
        audio_object_key: str,
        analysis_version: str,
        presentation_title: str | None = None,
        practice_type_code: str | None = None,
    ) -> AnalysisResultInput:
        downloaded = self._audio_storage.download(audio_object_key)
        try:
            normalized_path = self._audio_normalizer.normalize(downloaded.path)
        finally:
            downloaded.path.unlink(missing_ok=True)

        try:
            transcript = self._speech_transcriber.transcribe(normalized_path, language=self._language)
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
            assessment = self._pronunciation_assessor.assess(
                audio_path=normalized_path, calc_input=calc_input, language=self._language
            )
        finally:
            normalized_path.unlink(missing_ok=True)

        pronunciation_details = {"provider": assessment.provider}
        if assessment.fallback_reason is not None:
            pronunciation_details["fallbackReason"] = assessment.fallback_reason
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

        filler_detection = self._filler_detector.detect(calc_input)
        metrics = calc_all_metrics(
            calc_input,
            pronunciation_metric,
            filler_detection=filler_detection,
            fluency_override=fluency_override,
        )
        overall_score = calc_overall_score(metrics)
        total_speech_ms, total_silence_ms = calc_speech_silence_ms(calc_input)
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
                "feedbackFallbackReason": feedback_result.fallback_reason,
                "fillerDetector": filler_detection.detector,
                "fillerModel": filler_detection.model,
                "fillerPromptVersion": filler_detection.prompt_version,
                "fillerFallbackReason": filler_detection.fallback_reason,
            },
            metric_scores=metrics,
            feedback_items=feedback_result.feedback_items,
        )
