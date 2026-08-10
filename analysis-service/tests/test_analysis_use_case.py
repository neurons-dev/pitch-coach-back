from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

from app.application.analysis.analysis_use_case import AnalysisUseCase
from app.core.config import Settings
from app.domain.audio import DownloadedAudio, Transcript, TranscriptSegment
from app.domain.entities import AnalysisResultInput, PronunciationAssessment
from app.domain.errors import AnalysisError
from app.infrastructure.audio.normalizer import FfmpegAudioNormalizer
from app.infrastructure.audio.transcriber import FasterWhisperTranscriber
from app.infrastructure.feedback.template_generator import TemplateFeedbackGenerator
from app.infrastructure.pronunciation.local import LocalPronunciationAssessor


class _FakeAudioStorage:
    def __init__(self, path: Path) -> None:
        self._path = path
        self.download_calls: list[str] = []

    def download(self, object_key: str) -> DownloadedAudio:
        self.download_calls.append(object_key)
        self._path.write_bytes(b"raw-audio-bytes")
        return DownloadedAudio(path=self._path, content_type="audio/wav", size_bytes=100, duration_ms=5000)


class _FailingAudioStorage:
    def download(self, object_key: str) -> DownloadedAudio:
        raise AnalysisError(code="AUDIO_DOWNLOAD_FAILED", message="boom", retryable=True)


class _FakeAudioNormalizer:
    def __init__(self, path: Path) -> None:
        self._path = path
        self.normalize_calls: list[Path] = []

    def normalize(self, input_path: Path) -> Path:
        self.normalize_calls.append(input_path)
        self._path.write_bytes(b"normalized-audio-bytes")
        return self._path


class _FailingAudioNormalizer:
    def normalize(self, input_path: Path) -> Path:
        raise AnalysisError(code="AUDIO_NORMALIZATION_FAILED", message="boom", retryable=False)


class _FakeSpeechTranscriber:
    def __init__(self, transcript: Transcript) -> None:
        self._transcript = transcript
        self.transcribe_calls: list[tuple] = []

    def transcribe(self, audio_path: Path, *, language: str) -> Transcript:
        self.transcribe_calls.append((audio_path, language))
        return self._transcript


class _FailingSpeechTranscriber:
    def transcribe(self, audio_path: Path, *, language: str) -> Transcript:
        raise AnalysisError(code="STT_FAILED", message="boom", retryable=True)


class _FakePronunciationAssessor:
    def assess(self, *, audio_path, calc_input, language) -> PronunciationAssessment:
        return PronunciationAssessment(provider="fake", pronunciation_score=80)


class _FailingPronunciationAssessor:
    def assess(self, *, audio_path, calc_input, language) -> PronunciationAssessment:
        raise AnalysisError(code="PRONUNCIATION_PROVIDER_FAILED", message="boom", retryable=True)


def _transcript() -> Transcript:
    return Transcript(
        text="안녕하세요 오늘은 발표를 시작하겠습니다",
        language="ko",
        model_version="faster-whisper-tiny",
        duration_ms=5000,
        segments=[
            TranscriptSegment(start_ms=0, end_ms=2000, text="안녕하세요 오늘은", avg_logprob=-0.1),
            TranscriptSegment(start_ms=2000, end_ms=5000, text="발표를 시작하겠습니다", avg_logprob=-0.2),
        ],
    )


class TestAnalysisUseCaseFakeProviders:
    def _use_case(
        self, *, tmp_path: Path, storage=None, normalizer=None, transcriber=None, pronunciation_assessor=None
    ) -> tuple[AnalysisUseCase, Path, Path]:
        downloaded_path = tmp_path / "downloaded.bin"
        normalized_path = tmp_path / "normalized.wav"
        use_case = AnalysisUseCase(
            audio_storage=storage or _FakeAudioStorage(downloaded_path),
            audio_normalizer=normalizer or _FakeAudioNormalizer(normalized_path),
            speech_transcriber=transcriber or _FakeSpeechTranscriber(_transcript()),
            pronunciation_assessor=pronunciation_assessor or _FakePronunciationAssessor(),
            feedback_generator=TemplateFeedbackGenerator(),
            pipeline_version="audio-pipeline-v1",
        )
        return use_case, downloaded_path, normalized_path

    def test_run_returns_populated_analysis_result(self, tmp_path: Path):
        use_case, _, _ = self._use_case(tmp_path=tmp_path)

        result = use_case.run(audio_object_key="sessions/x/y.wav", analysis_version="v1")

        assert isinstance(result, AnalysisResultInput)
        assert result.pipeline_version == "audio-pipeline-v1"
        assert result.stt_model_version == "faster-whisper-tiny"
        assert result.scoring_rule_version == "coach-ko-v1"
        assert result.transcript_text == "안녕하세요 오늘은 발표를 시작하겠습니다"
        assert len(result.transcript_segments) == 2
        assert {m.metric_code for m in result.metric_scores} == {
            "SPEED", "FILLER", "STRUCTURE", "DELIVERY", "PRONUNCIATION", "FLUENCY",
        }
        assert result.feedback_items[0].item_type == "summary"
        assert result.model_info["feedbackPromptVersion"] == "template-feedback-v1"
        assert result.model_info["feedbackFallbackReason"] is None

    def test_run_cleans_up_downloaded_and_normalized_files_on_success(self, tmp_path: Path):
        use_case, downloaded_path, normalized_path = self._use_case(tmp_path=tmp_path)

        use_case.run(audio_object_key="sessions/x/y.wav", analysis_version="v1")

        assert not downloaded_path.exists()
        assert not normalized_path.exists()

    def test_run_propagates_download_error_without_touching_other_stages(self, tmp_path: Path):
        normalizer = _FakeAudioNormalizer(tmp_path / "normalized.wav")
        use_case, _, _ = self._use_case(tmp_path=tmp_path, storage=_FailingAudioStorage(), normalizer=normalizer)

        with pytest.raises(AnalysisError) as exc_info:
            use_case.run(audio_object_key="sessions/x/y.wav", analysis_version="v1")

        assert exc_info.value.code == "AUDIO_DOWNLOAD_FAILED"
        assert normalizer.normalize_calls == []

    def test_run_cleans_up_downloaded_file_when_normalize_fails(self, tmp_path: Path):
        use_case, downloaded_path, _ = self._use_case(tmp_path=tmp_path, normalizer=_FailingAudioNormalizer())

        with pytest.raises(AnalysisError) as exc_info:
            use_case.run(audio_object_key="sessions/x/y.wav", analysis_version="v1")

        assert exc_info.value.code == "AUDIO_NORMALIZATION_FAILED"
        assert not downloaded_path.exists()

    def test_run_cleans_up_normalized_file_when_transcribe_fails(self, tmp_path: Path):
        use_case, downloaded_path, normalized_path = self._use_case(
            tmp_path=tmp_path, transcriber=_FailingSpeechTranscriber()
        )

        with pytest.raises(AnalysisError) as exc_info:
            use_case.run(audio_object_key="sessions/x/y.wav", analysis_version="v1")

        assert exc_info.value.code == "STT_FAILED"
        assert not downloaded_path.exists()
        assert not normalized_path.exists()

    def test_run_cleans_up_normalized_file_when_pronunciation_assessment_fails(self, tmp_path: Path):
        use_case, downloaded_path, normalized_path = self._use_case(
            tmp_path=tmp_path, pronunciation_assessor=_FailingPronunciationAssessor()
        )

        with pytest.raises(AnalysisError) as exc_info:
            use_case.run(audio_object_key="sessions/x/y.wav", analysis_version="v1")

        assert exc_info.value.code == "PRONUNCIATION_PROVIDER_FAILED"
        assert not downloaded_path.exists()
        assert not normalized_path.exists()

    def test_run_uses_external_fluency_score_when_provided(self, tmp_path: Path):
        class _FluencyOverridingAssessor:
            def assess(self, *, audio_path, calc_input, language) -> PronunciationAssessment:
                return PronunciationAssessment(provider="azure", pronunciation_score=90, fluency_score=42)

        use_case, _, _ = self._use_case(
            tmp_path=tmp_path, pronunciation_assessor=_FluencyOverridingAssessor()
        )

        result = use_case.run(audio_object_key="sessions/x/y.wav", analysis_version="v1")

        fluency = next(m for m in result.metric_scores if m.metric_code == "FLUENCY")
        assert fluency.score == 42
        assert fluency.details == {"provider": "azure"}


class _LocalFileAudioStorage:
    def __init__(self, source_path: Path) -> None:
        self._source_path = source_path

    def download(self, object_key: str) -> DownloadedAudio:
        tmp_path = Path(tempfile.gettempdir()) / f"e2e-{uuid.uuid4().hex}.wav"
        tmp_path.write_bytes(self._source_path.read_bytes())
        return DownloadedAudio(
            path=tmp_path,
            content_type="audio/wav",
            size_bytes=tmp_path.stat().st_size,
            duration_ms=1000,
        )


def _settings(**overrides) -> Settings:
    values = {"database_url": "postgresql+psycopg://postgres:postgres@localhost/test"}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_end_to_end_with_real_ffmpeg_and_whisper(tmp_path: Path):
    raw_audio = tmp_path / "raw.wav"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1",
            "-ar", "44100",
            "-ac", "2",
            str(raw_audio),
        ],
        capture_output=True,
        check=True,
    )

    use_case = AnalysisUseCase(
        audio_storage=_LocalFileAudioStorage(raw_audio),
        audio_normalizer=FfmpegAudioNormalizer(),
        speech_transcriber=FasterWhisperTranscriber(settings=_settings(whisper_model_size="tiny")),
        pronunciation_assessor=LocalPronunciationAssessor(),
        feedback_generator=TemplateFeedbackGenerator(),
        pipeline_version="audio-pipeline-v1",
    )

    result = use_case.run(audio_object_key="sessions/x/y.wav", analysis_version="v1")

    assert isinstance(result, AnalysisResultInput)
    assert result.pipeline_version == "audio-pipeline-v1"
    assert result.stt_model_version == "faster-whisper-tiny"
    assert result.scoring_rule_version == "coach-ko-v1"
    assert len(result.metric_scores) == 6
    assert 0 <= result.overall_score <= 100
