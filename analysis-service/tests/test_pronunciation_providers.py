from __future__ import annotations

import pytest

from app.core.config import Settings
from app.infrastructure.pronunciation.azure_speech_sdk import AzureSpeechSdkPronunciationAssessor
from app.infrastructure.pronunciation.factory import create_pronunciation_assessor


def _settings(**overrides) -> Settings:
    values = {"database_url": "postgresql+psycopg://postgres:postgres@localhost/test"}
    values.update(overrides)
    return Settings(_env_file=None, **values)


class TestCreatePronunciationAssessor:
    def test_without_key_raises_config_error(self):
        with pytest.raises(ValueError, match="AZURE_SPEECH_KEY"):
            create_pronunciation_assessor(_settings())

    def test_with_key_returns_azure_assessor(self):
        assessor = create_pronunciation_assessor(_settings(azure_speech_key="k"))
        assert isinstance(assessor, AzureSpeechSdkPronunciationAssessor)
