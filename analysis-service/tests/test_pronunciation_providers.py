from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.domain.entities import MetricCalculationInput, PronunciationAssessment
from app.domain.errors import AnalysisError
from app.infrastructure.pronunciation.factory import create_pronunciation_assessor
from app.infrastructure.pronunciation.fallback import FallbackPronunciationAssessor
from app.infrastructure.pronunciation.local import LocalPronunciationAssessor


def _calc_input(text: str = "안녕하세요", duration_ms: int = 2000) -> MetricCalculationInput:
    return MetricCalculationInput(text=text, duration_ms=duration_ms, segments=[])


def _settings(**overrides) -> Settings:
    values = {"database_url": "postgresql+psycopg://postgres:postgres@localhost/test"}
    values.update(overrides)
    return Settings(_env_file=None, **values)


class TestFallbackPronunciationAssessor:
    def test_uses_primary_result_when_primary_succeeds(self, tmp_path: Path):
        audio_path = tmp_path / "a.wav"
        primary = MagicMock()
        primary.assess.return_value = PronunciationAssessment(provider="external", pronunciation_score=90)
        fallback = MagicMock()

        result = FallbackPronunciationAssessor(primary=primary, fallback=fallback).assess(
            audio_path=audio_path, calc_input=_calc_input(), language="ko-KR"
        )

        assert result.provider == "external"
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
            create_pronunciation_assessor(_settings(pronunciation_provider="azure", azure_speech_key=None))

    def test_azure_with_key_returns_fallback_wrapped_assessor(self):
        assessor = create_pronunciation_assessor(
            _settings(pronunciation_provider="azure", azure_speech_key="k")
        )
        assert isinstance(assessor, FallbackPronunciationAssessor)

    def test_unknown_provider_raises_config_error(self):
        with pytest.raises(ValueError, match="알 수 없는"):
            create_pronunciation_assessor(_settings(pronunciation_provider="bogus"))

    def test_default_provider_is_local(self):
        settings = _settings()
        assert settings.pronunciation_provider == "local"
