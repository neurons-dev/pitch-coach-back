from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import NamedTuple

import azure.cognitiveservices.speech as speechsdk

from app.domain.entities import MetricCalculationInput, PronunciationAssessment
from app.domain.errors import AnalysisError

logger = logging.getLogger(__name__)

_MIN_TIMEOUT_BUFFER_SECONDS = 30.0
_TIMEOUT_MULTIPLIER = 2.0
_RETRY_BACKOFF_SECONDS = (1.0, 3.0)


class _SegmentScores(NamedTuple):
    pronunciation: float
    fluency: float
    accuracy: float
    duration: int


def _extract_segment_scores(result: object, duration: int) -> _SegmentScores | None:
    """점수가 모두 채워진 세그먼트만 반환하고, 그렇지 않으면 None을 반환한다.

    Azure SDK의 PronunciationAssessmentResult는 응답 JSON에 PronunciationAssessment
    블록이 없으면 점수 속성을 아예 설정하지 않은 채 조용히 생성된다(무음이나 잡음만
    담긴 세그먼트 등). 이때 점수 프로퍼티 접근은 AttributeError를 내므로 getattr
    기본값으로 걸러 내고 해당 세그먼트를 집계에서 제외한다.
    """
    pronunciation = getattr(result, "pronunciation_score", None)
    fluency = getattr(result, "fluency_score", None)
    accuracy = getattr(result, "accuracy_score", None)
    if pronunciation is None or fluency is None or accuracy is None:
        return None
    return _SegmentScores(
        pronunciation=pronunciation,
        fluency=fluency,
        accuracy=accuracy,
        duration=duration,
    )


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
            except Exception as exc:
                # SDK 내부 예외가 그대로 새어 나가면 사용자에게 내부 속성명이 노출된다.
                logger.exception("Azure Speech 발음 평가 중 예상치 못한 오류")
                raise AnalysisError(
                    code="PRONUNCIATION_PROVIDER_FAILED",
                    message=f"Azure Speech 발음 평가 실패: {type(exc).__name__}",
                    retryable=False,
                ) from exc
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

        segment_scores: list[_SegmentScores] = []
        skipped_segments = 0
        cancellation_errors: list[str] = []
        done = threading.Event()

        def on_recognized(evt) -> None:
            nonlocal skipped_segments
            if evt.result.reason != speechsdk.ResultReason.RecognizedSpeech:
                return
            # 이 콜백은 SDK 스레드에서 실행되므로 예외가 나면 조용히 삼켜진다.
            # 세그먼트 하나 때문에 인식 전체가 유실되지 않도록 여기서 막는다.
            try:
                pron_result = speechsdk.PronunciationAssessmentResult(evt.result)
            except Exception:
                logger.warning("발음 평가 결과 생성 실패, 세그먼트 제외", exc_info=True)
                skipped_segments += 1
                return
            scores = _extract_segment_scores(pron_result, evt.result.duration)
            if scores is None:
                skipped_segments += 1
                return
            segment_scores.append(scores)

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
            logger.warning("Azure Speech 인식 취소 details=%s", cancellation_errors[0])
            raise AnalysisError(
                code="PRONUNCIATION_PROVIDER_FAILED",
                message="Azure Speech 인식 실패",
                retryable=True,
            )
        if not segment_scores:
            raise AnalysisError(
                code="PRONUNCIATION_PROVIDER_FAILED",
                message=(
                    "Azure Speech에서 발음 평가가 가능한 음성이 없습니다"
                    if skipped_segments
                    else "Azure Speech에서 인식된 음성이 없습니다"
                ),
                retryable=False,
            )
        if skipped_segments:
            logger.info(
                "발음 평가 결과가 없는 세그먼트 제외 skipped=%s used=%s",
                skipped_segments,
                len(segment_scores),
            )

        pronunciation_score = _weighted_average(
            [(scores.pronunciation, scores.duration) for scores in segment_scores]
        )
        fluency_score = _weighted_average(
            [(scores.fluency, scores.duration) for scores in segment_scores]
        )
        accuracy_score = _weighted_average(
            [(scores.accuracy, scores.duration) for scores in segment_scores]
        )

        return PronunciationAssessment(
            provider="azure",
            pronunciation_score=pronunciation_score,
            fluency_score=fluency_score,
            accuracy_score=accuracy_score,
            raw_response={
                "segmentCount": len(segment_scores),
                "skippedSegmentCount": skipped_segments,
            },
        )


def _weighted_average(scored: list[tuple[float, int]]) -> int:
    total_weight = sum(duration for _, duration in scored)
    if total_weight <= 0:
        return int(round(sum(score for score, _ in scored) / len(scored)))
    weighted_sum = sum(score * duration for score, duration in scored)
    return int(round(weighted_sum / total_weight))
