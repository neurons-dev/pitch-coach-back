from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.domain.audio import DownloadedAudio, Transcript
from app.domain.errors import AnalysisError
from app.infrastructure.audio.normalizer import FfmpegAudioNormalizer
from app.infrastructure.audio.storage import S3AudioStorage
from app.infrastructure.audio.transcriber import FasterWhisperTranscriber


def _settings(**overrides) -> Settings:
    values = {
        "database_url": "postgresql+psycopg://postgres:postgres@localhost/test",
        "s3_bucket": "pitch-coach-bucket",
        "aws_region": "ap-northeast-2",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def raw_audio_file(tmp_path: Path) -> Path:
    path = tmp_path / f"{uuid.uuid4().hex}.wav"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1",
            "-ar", "44100",
            "-ac", "2",
            str(path),
        ],
        capture_output=True,
        check=True,
    )
    return path


class TestFfmpegAudioNormalizer:
    def test_normalize_converts_to_mono_16khz_wav(self, raw_audio_file: Path):
        normalizer = FfmpegAudioNormalizer()

        output_path = normalizer.normalize(raw_audio_file)

        try:
            assert output_path.exists()
            assert output_path.stat().st_size > 0

            probe = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-select_streams", "a:0",
                    "-show_entries", "stream=channels,sample_rate",
                    "-of", "default=noprint_wrappers=1",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            fields = dict(line.split("=", 1) for line in probe.stdout.strip().splitlines())
            assert fields["channels"] == "1"
            assert fields["sample_rate"] == "16000"
        finally:
            output_path.unlink(missing_ok=True)

    def test_normalize_rejects_non_audio_input(self, tmp_path: Path):
        garbage = tmp_path / "not-audio.wav"
        garbage.write_bytes(b"this is definitely not an audio file")
        normalizer = FfmpegAudioNormalizer()

        with pytest.raises(AnalysisError) as exc_info:
            normalizer.normalize(garbage)
        assert exc_info.value.code == "AUDIO_NORMALIZATION_FAILED"
        assert exc_info.value.retryable is False


class TestS3AudioStorage:
    def test_download_returns_validated_audio(self, raw_audio_file: Path):
        def fake_download_file(bucket, key, dest):
            Path(dest).write_bytes(raw_audio_file.read_bytes())

        fake_client = MagicMock()
        fake_client.download_file.side_effect = fake_download_file

        with patch("app.infrastructure.audio.storage.boto3.client", return_value=fake_client):
            storage = S3AudioStorage(settings=_settings())

            result = storage.download("sessions/abc/audio.wav")

        try:
            assert isinstance(result, DownloadedAudio)
            assert result.content_type == "audio/wav"
            assert result.size_bytes > 0
            assert result.duration_ms > 0
            assert result.path.exists()
        finally:
            result.path.unlink(missing_ok=True)

    def test_download_rejects_unsupported_extension_without_calling_s3(self):
        fake_client = MagicMock()
        with patch("app.infrastructure.audio.storage.boto3.client", return_value=fake_client):
            storage = S3AudioStorage(settings=_settings())

            with pytest.raises(AnalysisError) as exc_info:
                storage.download("sessions/abc/notes.txt")
        assert exc_info.value.code == "AUDIO_FORMAT_NOT_SUPPORTED"
        assert exc_info.value.retryable is False
        fake_client.download_file.assert_not_called()

    def test_download_rejects_oversized_file_and_cleans_up(self, raw_audio_file: Path):
        def fake_download_file(bucket, key, dest):
            Path(dest).write_bytes(raw_audio_file.read_bytes())

        fake_client = MagicMock()
        fake_client.download_file.side_effect = fake_download_file

        with patch("app.infrastructure.audio.storage.boto3.client", return_value=fake_client):
            storage = S3AudioStorage(settings=_settings(audio_max_size_bytes=10))

            with pytest.raises(AnalysisError) as exc_info:
                storage.download("sessions/abc/audio.wav")

        assert exc_info.value.code == "AUDIO_TOO_LARGE"
        assert exc_info.value.retryable is False
        leftovers = list(Path(__import__("tempfile").gettempdir()).glob("analysis-*.wav"))
        assert leftovers == []

    def test_download_rejects_too_long_audio(self, raw_audio_file: Path):
        def fake_download_file(bucket, key, dest):
            Path(dest).write_bytes(raw_audio_file.read_bytes())

        fake_client = MagicMock()
        fake_client.download_file.side_effect = fake_download_file

        with patch("app.infrastructure.audio.storage.boto3.client", return_value=fake_client):
            storage = S3AudioStorage(settings=_settings(audio_max_duration_ms=100))

            with pytest.raises(AnalysisError) as exc_info:
                storage.download("sessions/abc/audio.wav")

        assert exc_info.value.code == "AUDIO_TOO_LONG"
        assert exc_info.value.retryable is False

    def test_download_wraps_s3_client_error_as_retryable(self):
        fake_client = MagicMock()
        fake_client.download_file.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "GetObject"
        )

        with patch("app.infrastructure.audio.storage.boto3.client", return_value=fake_client):
            storage = S3AudioStorage(settings=_settings())

            with pytest.raises(AnalysisError) as exc_info:
                storage.download("sessions/abc/audio.wav")

        assert exc_info.value.code == "AUDIO_DOWNLOAD_FAILED"
        assert exc_info.value.retryable is True


class TestFasterWhisperTranscriber:
    def test_transcriber_requests_and_maps_word_timestamps(self, tmp_path: Path):
        # given
        audio_path = tmp_path / "audio.wav"
        audio_path.write_bytes(b"fake")
        fake_model = MagicMock()
        fake_model.transcribe.return_value = (
            iter(
                [
                    SimpleNamespace(
                        start=0.0,
                        end=1.2,
                        text=" 음 시작합니다",
                        avg_logprob=-0.1,
                        words=[
                            SimpleNamespace(
                                start=0.1, end=0.3, word=" 음", probability=0.92
                            ),
                            SimpleNamespace(
                                start=0.8,
                                end=1.2,
                                word=" 시작합니다",
                                probability=0.95,
                            ),
                        ],
                    )
                ]
            ),
            SimpleNamespace(duration=1.2),
        )
        transcriber = FasterWhisperTranscriber(settings=_settings())
        transcriber._model = fake_model

        # when
        result = transcriber._run_transcribe(audio_path, "ko-KR")

        # then
        assert fake_model.transcribe.call_args.kwargs["word_timestamps"] is True
        assert [(word.text, word.start_ms, word.end_ms) for word in result.segments[0].words] == [
            ("음", 100, 300),
            ("시작합니다", 800, 1200),
        ]

    def test_transcribe_returns_transcript_with_model_version_and_duration(
        self, raw_audio_file: Path
    ):
        transcriber = FasterWhisperTranscriber(
            settings=_settings(whisper_model_size="tiny", stt_timeout_seconds=120)
        )

        result = transcriber.transcribe(raw_audio_file, language="ko-KR")

        assert isinstance(result, Transcript)
        assert result.model_version == "faster-whisper-tiny"
        assert result.language == "ko"
        assert result.duration_ms > 0
        assert isinstance(result.segments, list)

    def test_transcribe_raises_stt_timeout_when_budget_exceeded(self, raw_audio_file: Path):
        transcriber = FasterWhisperTranscriber(
            settings=_settings(whisper_model_size="tiny", stt_timeout_seconds=0.001)
        )

        with pytest.raises(AnalysisError) as exc_info:
            transcriber.transcribe(raw_audio_file, language="ko-KR")
        assert exc_info.value.code == "STT_TIMEOUT"
        assert exc_info.value.retryable is True

    def test_transcribe_wraps_model_failure_as_retryable(self, raw_audio_file: Path):
        transcriber = FasterWhisperTranscriber(settings=_settings(whisper_model_size="tiny"))
        broken_model = MagicMock()
        broken_model.transcribe.side_effect = RuntimeError("boom")
        transcriber._model = broken_model

        with pytest.raises(AnalysisError) as exc_info:
            transcriber.transcribe(raw_audio_file, language="ko-KR")
        assert exc_info.value.code == "STT_FAILED"
        assert exc_info.value.retryable is True
