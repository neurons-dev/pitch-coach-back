from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.config import Settings
from app.domain.entities import MetricCalculationInput, PronunciationAssessment
from app.domain.errors import AnalysisError
from app.infrastructure.pronunciation.azure import AzurePronunciationAssessor
from app.infrastructure.pronunciation.clova import ClovaPronunciationAssessor, _weighted_average
from app.infrastructure.pronunciation.factory import create_pronunciation_assessor
from app.infrastructure.pronunciation.fallback import FallbackPronunciationAssessor
from app.infrastructure.pronunciation.local import LocalPronunciationAssessor


def _calc_input(text: str = "안녕하세요", duration_ms: int = 2000) -> MetricCalculationInput:
    return MetricCalculationInput(text=text, duration_ms=duration_ms, segments=[])


def _settings(**overrides) -> Settings:
    values = {"database_url": "postgresql+psycopg://postgres:postgres@localhost/test"}
    values.update(overrides)
    return Settings(_env_file=None, **values)


class TestAzurePronunciationAssessor:
    def test_assess_parses_scores_from_response(self, tmp_path: Path):
        audio_path = tmp_path / "a.wav"
        audio_path.write_bytes(b"fake-audio")
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {
            "NBest": [
                {
                    "PronunciationAssessment": {
                        "PronScore": 88.4,
                        "AccuracyScore": 90.0,
                        "FluencyScore": 85.0,
                        "CompletenessScore": 95.0,
                    }
                }
            ]
        }

        with patch(
            "app.infrastructure.pronunciation.azure.httpx.post", return_value=fake_response
        ) as mock_post:
            assessor = AzurePronunciationAssessor(
                subscription_key="secret-key-123", region="koreacentral", timeout_seconds=5
            )
            result = assessor.assess(
                audio_path=audio_path, calc_input=_calc_input(), language="ko-KR"
            )

        assert result.provider == "azure"
        assert result.pronunciation_score == 88
        assert result.fluency_score == 85
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Ocp-Apim-Subscription-Key"] == "secret-key-123"

    def test_assess_raises_after_retries_without_leaking_key(self, tmp_path: Path):
        audio_path = tmp_path / "a.wav"
        audio_path.write_bytes(b"fake-audio")

        with patch(
            "app.infrastructure.pronunciation.azure.httpx.post",
            side_effect=httpx.ConnectTimeout("timed out"),
        ) as mock_post, patch("app.infrastructure.pronunciation.azure.time.sleep"):
            assessor = AzurePronunciationAssessor(
                subscription_key="super-secret",
                region="koreacentral",
                timeout_seconds=5,
                max_retries=2,
            )
            with pytest.raises(AnalysisError) as exc_info:
                assessor.assess(audio_path=audio_path, calc_input=_calc_input(), language="ko-KR")

        assert exc_info.value.code == "PRONUNCIATION_PROVIDER_FAILED"
        assert "super-secret" not in exc_info.value.message
        assert mock_post.call_count == 3

    def test_assess_raises_when_response_missing_pron_score(self, tmp_path: Path):
        audio_path = tmp_path / "a.wav"
        audio_path.write_bytes(b"fake-audio")
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"NBest": [{"PronunciationAssessment": {}}]}

        with patch(
            "app.infrastructure.pronunciation.azure.httpx.post", return_value=fake_response
        ), patch("app.infrastructure.pronunciation.azure.time.sleep"):
            assessor = AzurePronunciationAssessor(
                subscription_key="k", region="koreacentral", timeout_seconds=5, max_retries=0
            )
            with pytest.raises(AnalysisError) as exc_info:
                assessor.assess(audio_path=audio_path, calc_input=_calc_input(), language="ko-KR")

        assert exc_info.value.code == "PRONUNCIATION_PROVIDER_FAILED"


class TestClovaWeightedAverage:
    def test_single_score_returned_as_is(self):
        assert _weighted_average([(80, 1000)]) == 80

    def test_weights_by_chunk_duration(self):
        assert _weighted_average([(90, 1000), (60, 3000)]) == 68

    def test_falls_back_to_plain_average_when_durations_are_zero(self):
        assert _weighted_average([(80, 0), (60, 0)]) == 70


class TestClovaPronunciationAssessor:
    def test_short_audio_calls_api_once(self, tmp_path: Path):
        audio_path = tmp_path / "short.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(audio_path)],
            capture_output=True,
            check=True,
        )
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"pronunciationScore": 75}

        with patch(
            "app.infrastructure.pronunciation.clova.httpx.post", return_value=fake_response
        ) as mock_post:
            assessor = ClovaPronunciationAssessor(
                invoke_url="https://example.com/invoke",
                secret_key="clova-secret",
                timeout_seconds=5,
                max_chunk_seconds=55,
            )
            result = assessor.assess(
                audio_path=audio_path, calc_input=_calc_input(), language="ko-KR"
            )

        assert result.provider == "clova"
        assert result.pronunciation_score == 75
        assert mock_post.call_count == 1
        assert audio_path.exists()

    def test_long_audio_is_split_into_chunks_and_aggregated(self, tmp_path: Path):
        audio_path = tmp_path / "long.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=5", str(audio_path)],
            capture_output=True,
            check=True,
        )
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"pronunciationScore": 80}

        with patch(
            "app.infrastructure.pronunciation.clova.httpx.post", return_value=fake_response
        ) as mock_post:
            assessor = ClovaPronunciationAssessor(
                invoke_url="https://example.com/invoke",
                secret_key="clova-secret",
                timeout_seconds=5,
                max_chunk_seconds=2,
            )
            result = assessor.assess(
                audio_path=audio_path, calc_input=_calc_input(), language="ko-KR"
            )

        assert result.provider == "clova"
        assert mock_post.call_count >= 3
        assert result.raw_response["chunkCount"] == mock_post.call_count
        assert audio_path.exists()
        leftover_chunk_dirs = list(Path(tempfile.gettempdir()).glob("clova-chunks-*"))
        assert leftover_chunk_dirs == []


class TestFallbackPronunciationAssessor:
    def test_uses_primary_result_when_primary_succeeds(self, tmp_path: Path):
        audio_path = tmp_path / "a.wav"
        primary = MagicMock()
        primary.assess.return_value = PronunciationAssessment(provider="azure", pronunciation_score=90)
        fallback = MagicMock()

        result = FallbackPronunciationAssessor(primary=primary, fallback=fallback).assess(
            audio_path=audio_path, calc_input=_calc_input(), language="ko-KR"
        )

        assert result.provider == "azure"
        assert result.pronunciation_score == 90
        fallback.assess.assert_not_called()

    def test_falls_back_to_local_when_primary_raises(self, tmp_path: Path):
        audio_path = tmp_path / "a.wav"
        primary = MagicMock()
        primary.assess.side_effect = AnalysisError(
            code="PRONUNCIATION_PROVIDER_FAILED", message="boom", retryable=True
        )
        fallback = MagicMock()
        fallback.assess.return_value = PronunciationAssessment(provider="local", pronunciation_score=70)

        result = FallbackPronunciationAssessor(primary=primary, fallback=fallback).assess(
            audio_path=audio_path, calc_input=_calc_input(), language="ko-KR"
        )

        assert result.provider == "local"
        assert result.fallback_reason == "AnalysisError"


class TestCreatePronunciationAssessor:
    def test_local_provider_returns_local_assessor(self):
        assessor = create_pronunciation_assessor(_settings(pronunciation_provider="local"))
        assert isinstance(assessor, LocalPronunciationAssessor)

    def test_azure_without_key_raises_config_error(self):
        with pytest.raises(ValueError, match="AZURE_SPEECH_KEY"):
            create_pronunciation_assessor(_settings(pronunciation_provider="azure"))

    def test_azure_with_key_returns_fallback_wrapped_assessor(self):
        assessor = create_pronunciation_assessor(
            _settings(pronunciation_provider="azure", azure_speech_key="k")
        )
        assert isinstance(assessor, FallbackPronunciationAssessor)

    def test_clova_without_config_raises_config_error(self):
        with pytest.raises(ValueError, match="CLOVA_INVOKE_URL"):
            create_pronunciation_assessor(_settings(pronunciation_provider="clova"))

    def test_clova_with_config_returns_fallback_wrapped_assessor(self):
        assessor = create_pronunciation_assessor(
            _settings(
                pronunciation_provider="clova",
                clova_invoke_url="https://example.com/invoke",
                clova_secret_key="s",
            )
        )
        assert isinstance(assessor, FallbackPronunciationAssessor)

    def test_unknown_provider_raises_config_error(self):
        with pytest.raises(ValueError, match="알 수 없는"):
            create_pronunciation_assessor(_settings(pronunciation_provider="bogus"))
