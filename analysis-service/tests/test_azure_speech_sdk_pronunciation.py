from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.domain.entities import MetricCalculationInput
from app.domain.errors import AnalysisError
from app.infrastructure.pronunciation.azure_speech_sdk import (
    AzureSpeechSdkPronunciationAssessor,
    _weighted_average,
)


def _calc_input(duration_ms: int = 5000) -> MetricCalculationInput:
    return MetricCalculationInput(text="안녕하세요", duration_ms=duration_ms, segments=[])


class _FakeEventSource:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback

    def fire(self, evt) -> None:
        if self.callback is not None:
            self.callback(evt)


class _FakeRecognizer:
    """Simulates the SDK recognizer: firing events synchronously when
    start_continuous_recognition() is called, in place of the real
    background-thread-driven behavior."""

    def __init__(self, *, events: list[tuple[str, object]]) -> None:
        self.recognized = _FakeEventSource()
        self.canceled = _FakeEventSource()
        self.session_stopped = _FakeEventSource()
        self._events = events
        self.stopped_called = False

    def start_continuous_recognition(self) -> None:
        for kind, evt in self._events:
            getattr(self, kind).fire(evt)

    def stop_continuous_recognition(self) -> None:
        self.stopped_called = True


def _recognized_result_event(*, duration: int) -> SimpleNamespace:
    return SimpleNamespace(
        result=SimpleNamespace(reason="RECOGNIZED", duration=duration)
    )


def _canceled_event(*, is_error: bool, error_details: str = "boom") -> SimpleNamespace:
    return SimpleNamespace(
        cancellation_details=SimpleNamespace(
            reason="ERROR" if is_error else "END_OF_STREAM",
            error_details=error_details,
        )
    )


def _pronunciation_result(*, pronunciation: float, fluency: float, accuracy: float):
    return SimpleNamespace(
        pronunciation_score=pronunciation, fluency_score=fluency, accuracy_score=accuracy
    )



class _UnassessedPronunciationResult:
    """평가 JSON이 없을 때의 실제 SDK 객체를 흉내낸다.

    Azure SDK는 응답에 PronunciationAssessment 블록이 없으면 점수 속성을 세팅하지
    않으므로, 점수 프로퍼티 접근이 AttributeError(_pronunciation_score 없음)를 낸다.
    """

    @property
    def pronunciation_score(self) -> float:
        raise AttributeError(
            "'PronunciationAssessmentResult' object has no attribute '_pronunciation_score'"
        )

    @property
    def fluency_score(self) -> float:
        raise AttributeError(
            "'PronunciationAssessmentResult' object has no attribute '_fluency_score'"
        )

    @property
    def accuracy_score(self) -> float:
        raise AttributeError(
            "'PronunciationAssessmentResult' object has no attribute '_accuracy_score'"
        )


def _patch_speechsdk():
    return patch("app.infrastructure.pronunciation.azure_speech_sdk.speechsdk")


class TestWeightedAverage:
    def test_single_score_returned_as_is(self):
        # given / when / then
        assert _weighted_average([(80, 1000)]) == 80

    def test_weights_by_duration(self):
        # given / when / then
        assert _weighted_average([(90, 1000), (60, 3000)]) == 68

    def test_falls_back_to_plain_average_when_durations_are_zero(self):
        # given / when / then
        assert _weighted_average([(80, 0), (60, 0)]) == 70


class TestAzureSpeechSdkPronunciationAssessor:
    def _assessor(self) -> AzureSpeechSdkPronunciationAssessor:
        return AzureSpeechSdkPronunciationAssessor(
            subscription_key="secret-key", region="koreacentral", timeout_seconds=5
        )

    def test_assess_aggregates_multiple_segments_weighted_by_duration(self, tmp_path: Path):
        # given
        audio_path = tmp_path / "a.wav"
        audio_path.write_bytes(b"fake")
        events = [
            ("recognized", _recognized_result_event(duration=10_000_000)),
            ("recognized", _recognized_result_event(duration=30_000_000)),
            ("session_stopped", SimpleNamespace()),
        ]
        fake_recognizer = _FakeRecognizer(events=events)
        pron_results = [
            _pronunciation_result(pronunciation=90, fluency=80, accuracy=95),
            _pronunciation_result(pronunciation=60, fluency=50, accuracy=65),
        ]

        with _patch_speechsdk() as mock_speechsdk:
            mock_speechsdk.SpeechRecognizer.return_value = fake_recognizer
            mock_speechsdk.PronunciationAssessmentResult.side_effect = pron_results
            mock_speechsdk.ResultReason.RecognizedSpeech = "RECOGNIZED"
            mock_speechsdk.CancellationReason.Error = "ERROR"

            # when
            result = self._assessor().assess(
                audio_path=audio_path, calc_input=_calc_input(), language="ko-KR"
            )

        # then
        assert result.provider == "azure"
        assert result.pronunciation_score == 68  # weighted: (90*1 + 60*3) / 4
        assert result.fluency_score == 58  # weighted: (80*1 + 50*3) / 4
        assert result.accuracy_score == 72  # weighted: (95*1 + 65*3) / 4 = 72.5 -> 72 (round-half-to-even)
        assert fake_recognizer.stopped_called is True

    def test_assess_retries_then_raises_on_persistent_timeout(self, tmp_path: Path):
        # given
        audio_path = tmp_path / "a.wav"
        audio_path.write_bytes(b"fake")
        fake_recognizer = _FakeRecognizer(events=[])  # never fires session_stopped/canceled

        with _patch_speechsdk() as mock_speechsdk, patch(
            "app.infrastructure.pronunciation.azure_speech_sdk.threading.Event"
        ) as mock_event_cls, patch(
            "app.infrastructure.pronunciation.azure_speech_sdk.time.sleep"
        ):
            mock_speechsdk.SpeechRecognizer.return_value = fake_recognizer
            mock_speechsdk.ResultReason.RecognizedSpeech = "RECOGNIZED"
            mock_speechsdk.CancellationReason.Error = "ERROR"
            mock_event = MagicMock()
            mock_event.wait.return_value = False  # simulate timeout without any real delay
            mock_event_cls.return_value = mock_event

            assessor = AzureSpeechSdkPronunciationAssessor(
                subscription_key="k", region="koreacentral", timeout_seconds=0.1, max_retries=1
            )

            # when
            with pytest.raises(AnalysisError) as exc_info:
                assessor.assess(audio_path=audio_path, calc_input=_calc_input(), language="ko-KR")

        # then
        assert exc_info.value.code == "PRONUNCIATION_PROVIDER_FAILED"
        assert exc_info.value.retryable is True
        assert mock_speechsdk.SpeechRecognizer.call_count == 2  # initial attempt + 1 retry

    def test_assess_raises_on_cancellation_error_without_leaking_key(self, tmp_path: Path):
        # given
        audio_path = tmp_path / "a.wav"
        audio_path.write_bytes(b"fake")
        events = [("canceled", _canceled_event(is_error=True, error_details="super-secret leak"))]
        fake_recognizer = _FakeRecognizer(events=events)

        with _patch_speechsdk() as mock_speechsdk, patch(
            "app.infrastructure.pronunciation.azure_speech_sdk.time.sleep"
        ):
            mock_speechsdk.SpeechRecognizer.return_value = fake_recognizer
            mock_speechsdk.ResultReason.RecognizedSpeech = "RECOGNIZED"
            mock_speechsdk.CancellationReason.Error = "ERROR"

            # when
            with pytest.raises(AnalysisError) as exc_info:
                self._assessor().assess(
                    audio_path=audio_path, calc_input=_calc_input(), language="ko-KR"
                )

        # then
        assert exc_info.value.code == "PRONUNCIATION_PROVIDER_FAILED"
        assert "super-secret leak" not in exc_info.value.message
        assert "secret-key" not in exc_info.value.message

    def test_assess_raises_when_no_speech_recognized(self, tmp_path: Path):
        # given
        audio_path = tmp_path / "a.wav"
        audio_path.write_bytes(b"fake")
        events = [("session_stopped", SimpleNamespace())]
        fake_recognizer = _FakeRecognizer(events=events)

        with _patch_speechsdk() as mock_speechsdk:
            mock_speechsdk.SpeechRecognizer.return_value = fake_recognizer
            mock_speechsdk.ResultReason.RecognizedSpeech = "RECOGNIZED"
            mock_speechsdk.CancellationReason.Error = "ERROR"

            # when
            with pytest.raises(AnalysisError) as exc_info:
                self._assessor().assess(
                    audio_path=audio_path, calc_input=_calc_input(), language="ko-KR"
                )

        # then
        assert exc_info.value.code == "PRONUNCIATION_PROVIDER_FAILED"
        assert exc_info.value.retryable is False

    def test_assess_skips_segments_without_pronunciation_assessment(self, tmp_path: Path):
        # given: 평가 결과가 붙지 않은 세그먼트가 섞여 들어온다
        audio_path = tmp_path / "a.wav"
        audio_path.write_bytes(b"fake")
        events = [
            ("recognized", _recognized_result_event(duration=10_000_000)),
            ("recognized", _recognized_result_event(duration=30_000_000)),
            ("session_stopped", SimpleNamespace()),
        ]
        fake_recognizer = _FakeRecognizer(events=events)
        pron_results = [
            _UnassessedPronunciationResult(),
            _pronunciation_result(pronunciation=60, fluency=50, accuracy=65),
        ]

        with _patch_speechsdk() as mock_speechsdk:
            mock_speechsdk.SpeechRecognizer.return_value = fake_recognizer
            mock_speechsdk.PronunciationAssessmentResult.side_effect = pron_results
            mock_speechsdk.ResultReason.RecognizedSpeech = "RECOGNIZED"
            mock_speechsdk.CancellationReason.Error = "ERROR"

            # when
            result = self._assessor().assess(
                audio_path=audio_path, calc_input=_calc_input(), language="ko-KR"
            )

        # then: 평가된 세그먼트만으로 집계하고, 제외 건수를 남긴다
        assert result.pronunciation_score == 60
        assert result.fluency_score == 50
        assert result.accuracy_score == 65
        assert result.raw_response == {"segmentCount": 1, "skippedSegmentCount": 1}

    def test_assess_fails_cleanly_when_no_segment_has_pronunciation_assessment(
        self, tmp_path: Path
    ):
        # given: 인식은 됐지만 어떤 세그먼트에도 평가 결과가 없다
        audio_path = tmp_path / "a.wav"
        audio_path.write_bytes(b"fake")
        events = [
            ("recognized", _recognized_result_event(duration=10_000_000)),
            ("session_stopped", SimpleNamespace()),
        ]
        fake_recognizer = _FakeRecognizer(events=events)

        with _patch_speechsdk() as mock_speechsdk:
            mock_speechsdk.SpeechRecognizer.return_value = fake_recognizer
            mock_speechsdk.PronunciationAssessmentResult.return_value = (
                _UnassessedPronunciationResult()
            )
            mock_speechsdk.ResultReason.RecognizedSpeech = "RECOGNIZED"
            mock_speechsdk.CancellationReason.Error = "ERROR"

            # when / then: AttributeError가 새어 나가지 않고 도메인 오류로 바뀐다
            with pytest.raises(AnalysisError) as exc_info:
                self._assessor().assess(
                    audio_path=audio_path, calc_input=_calc_input(), language="ko-KR"
                )

        assert exc_info.value.code == "PRONUNCIATION_PROVIDER_FAILED"
        assert exc_info.value.retryable is False
        assert "_pronunciation_score" not in exc_info.value.message

    def test_assess_wraps_unexpected_sdk_error_into_analysis_error(self, tmp_path: Path):
        # given
        audio_path = tmp_path / "a.wav"
        audio_path.write_bytes(b"fake")

        with _patch_speechsdk() as mock_speechsdk:
            mock_speechsdk.SpeechRecognizer.side_effect = RuntimeError("sdk exploded")

            # when / then
            with pytest.raises(AnalysisError) as exc_info:
                self._assessor().assess(
                    audio_path=audio_path, calc_input=_calc_input(), language="ko-KR"
                )

        assert exc_info.value.code == "PRONUNCIATION_PROVIDER_FAILED"
        assert "sdk exploded" not in exc_info.value.message

    def test_assess_scales_timeout_with_audio_duration(self, tmp_path: Path):
        # given
        audio_path = tmp_path / "a.wav"
        audio_path.write_bytes(b"fake")
        events = [
            ("recognized", _recognized_result_event(duration=10_000_000)),
            ("session_stopped", SimpleNamespace()),
        ]
        fake_recognizer = _FakeRecognizer(events=events)

        with _patch_speechsdk() as mock_speechsdk, patch(
            "app.infrastructure.pronunciation.azure_speech_sdk.threading.Event"
        ) as mock_event_cls:
            mock_speechsdk.SpeechRecognizer.return_value = fake_recognizer
            mock_speechsdk.PronunciationAssessmentResult.return_value = _pronunciation_result(
                pronunciation=80, fluency=80, accuracy=80
            )
            mock_speechsdk.ResultReason.RecognizedSpeech = "RECOGNIZED"
            mock_speechsdk.CancellationReason.Error = "ERROR"
            mock_event = MagicMock()
            mock_event.wait.return_value = True
            mock_event_cls.return_value = mock_event
            long_calc_input = _calc_input(duration_ms=600_000)  # 10 minutes

            # when
            AzureSpeechSdkPronunciationAssessor(
                subscription_key="k", region="koreacentral", timeout_seconds=5
            ).assess(audio_path=audio_path, calc_input=long_calc_input, language="ko-KR")

        # then
        called_timeout = mock_event.wait.call_args.kwargs["timeout"]
        assert called_timeout > 5  # base timeout must be scaled up for long audio
