from __future__ import annotations

import threading
import time
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk

from app.domain.entities import MetricCalculationInput, PronunciationAssessment
from app.domain.errors import AnalysisError

_MIN_TIMEOUT_BUFFER_SECONDS = 30.0
_TIMEOUT_MULTIPLIER = 2.0
_RETRY_BACKOFF_SECONDS = (1.0, 3.0)


class AzureSpeechSdkPronunciationAssessor:
    def __init__(
        self,
        *,
        subscription_key: str,
        region: str,
        timeout_seconds: float,
        max_retries: int = 1,
    ) -> None:
        self._subscription_key = subscription_key
        self._region = region
        self._base_timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    def assess(
        self, *, audio_path: Path, calc_input: MetricCalculationInput, language: str
    ) -> PronunciationAssessment:
        last_error: AnalysisError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return self._attempt(audio_path=audio_path, calc_input=calc_input, language=language)
            except AnalysisError as exc:
                last_error = exc
                if not exc.retryable or attempt >= self._max_retries:
                    raise
                time.sleep(_RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)])
        raise last_error  # pragma: no cover - loop always returns or raises above

    def _attempt(
        self, *, audio_path: Path, calc_input: MetricCalculationInput, language: str
    ) -> PronunciationAssessment:
        speech_config = speechsdk.SpeechConfig(
            subscription=self._subscription_key, region=self._region
        )
        speech_config.speech_recognition_language = language

        # continuous recognition (30초 초과 발표)에서는 EnableMiscue가 지원되지 않는다.
        # https://learn.microsoft.com/azure/ai-services/speech-service/how-to-pronunciation-assessment
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text="",
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=False,
        )

        audio_config = speechsdk.audio.AudioConfig(filename=str(audio_path))
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, audio_config=audio_config
        )
        pronunciation_config.apply_to(recognizer)

        segment_results: list[tuple[object, int]] = []
        cancellation_errors: list[str] = []
        done = threading.Event()

        def on_recognized(evt) -> None:
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                pron_result = speechsdk.PronunciationAssessmentResult(evt.result)
                segment_results.append((pron_result, evt.result.duration))

        def on_canceled(evt) -> None:
            if evt.cancellation_details.reason == speechsdk.CancellationReason.Error:
                cancellation_errors.append(evt.cancellation_details.error_details)
            done.set()

        def on_stopped(_evt) -> None:
            done.set()

        recognizer.recognized.connect(on_recognized)
        recognizer.canceled.connect(on_canceled)
        recognizer.session_stopped.connect(on_stopped)

        timeout_seconds = max(
            self._base_timeout_seconds,
            (calc_input.duration_ms / 1000) * _TIMEOUT_MULTIPLIER + _MIN_TIMEOUT_BUFFER_SECONDS,
        )

        recognizer.start_continuous_recognition()
        finished = done.wait(timeout=timeout_seconds)
        recognizer.stop_continuous_recognition()

        if not finished:
            raise AnalysisError(
                code="PRONUNCIATION_PROVIDER_FAILED",
                message="Azure Speech 인식 시간 초과",
                retryable=True,
            )
        if cancellation_errors:
            raise AnalysisError(
                code="PRONUNCIATION_PROVIDER_FAILED",
                message="Azure Speech 인식 실패",
                retryable=True,
            )
        if not segment_results:
            raise AnalysisError(
                code="PRONUNCIATION_PROVIDER_FAILED",
                message="Azure Speech에서 인식된 음성이 없습니다",
                retryable=False,
            )

        pronunciation_score = _weighted_average(
            [(result.pronunciation_score, duration) for result, duration in segment_results]
        )
        fluency_score = _weighted_average(
            [(result.fluency_score, duration) for result, duration in segment_results]
        )
        accuracy_score = _weighted_average(
            [(result.accuracy_score, duration) for result, duration in segment_results]
        )

        return PronunciationAssessment(
            provider="azure",
            pronunciation_score=pronunciation_score,
            fluency_score=fluency_score,
            accuracy_score=accuracy_score,
            raw_response={"segmentCount": len(segment_results)},
        )


def _weighted_average(scored: list[tuple[float, int]]) -> int:
    total_weight = sum(duration for _, duration in scored)
    if total_weight <= 0:
        return int(round(sum(score for score, _ in scored) / len(scored)))
    weighted_sum = sum(score * duration for score, duration in scored)
    return int(round(weighted_sum / total_weight))
