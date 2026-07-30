from __future__ import annotations

from app.domain.audio import AudioNormalizer, AudioStorage, SpeechTranscriber
from app.domain.entities import (
    AnalysisResultInput,
    MetricCalculationInput,
    TranscriptSegmentFeatures,
)
from app.domain.feedback import build_coach_comment, build_feedback_items
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
        pipeline_version: str,
        language: str = _DEFAULT_LANGUAGE,
    ) -> None:
        self._audio_storage = audio_storage
        self._audio_normalizer = audio_normalizer
        self._speech_transcriber = speech_transcriber
        self._pronunciation_assessor = pronunciation_assessor
        self._pipeline_version = pipeline_version
        self._language = language

    def run(self, *, audio_object_key: str, analysis_version: str) -> AnalysisResultInput:
        downloaded = self._audio_storage.download(audio_object_key)
        try:
            normalized_path = self._audio_normalizer.normalize(downloaded.path)
        finally:
            downloaded.path.unlink(missing_ok=True)

        try:
            transcript = self._speech_transcriber.transcribe(normalized_path, language=self._language)
        finally:
            normalized_path.unlink(missing_ok=True)

        calc_input = MetricCalculationInput(
            text=transcript.text,
            duration_ms=transcript.duration_ms,
            segments=[
                TranscriptSegmentFeatures(
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    text=segment.text,
                    avg_logprob=segment.avg_logprob,
                )
                for segment in transcript.segments
            ],
        )

        metrics = calc_all_metrics(calc_input, self._pronunciation_assessor)
        overall_score = calc_overall_score(metrics)
        total_speech_ms, total_silence_ms = calc_speech_silence_ms(calc_input)
        coach_comment = build_coach_comment(overall_score, metrics)
        feedback_items = build_feedback_items(overall_score, coach_comment, metrics)

        return AnalysisResultInput(
            overall_score=overall_score,
            pipeline_version=self._pipeline_version,
            stt_model_version=transcript.model_version,
            scoring_rule_version=SCORING_RULE_VERSION,
            coach_comment=coach_comment,
            transcript_text=transcript.text,
            transcript_segments=[
                {"startMs": segment.start_ms, "endMs": segment.end_ms, "text": segment.text}
                for segment in transcript.segments
            ],
            total_speech_ms=total_speech_ms,
            total_silence_ms=total_silence_ms,
            model_info={"language": transcript.language},
            metric_scores=metrics,
            feedback_items=feedback_items,
        )
