from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import httpx

from app.domain.entities import MetricCalculationInput, PronunciationAssessment
from app.domain.errors import AnalysisError

_RETRY_BACKOFF_SECONDS = (0.5, 1.5)


class AzurePronunciationAssessor:
    def __init__(
        self,
        *,
        subscription_key: str,
        region: str,
        timeout_seconds: float,
        max_retries: int = 2,
    ) -> None:
        self._subscription_key = subscription_key
        self._region = region
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    def assess(
        self, *, audio_path: Path, calc_input: MetricCalculationInput, language: str
    ) -> PronunciationAssessment:
        url = (
            f"https://{self._region}.stt.speech.microsoft.com"
            "/speech/recognition/conversation/cognitiveservices/v1"
        )
        pronunciation_config = base64.b64encode(
            json.dumps(
                {
                    "ReferenceText": calc_input.text,
                    "GradingSystem": "HundredMark",
                    "Granularity": "Phoneme",
                    "EnableMiscue": True,
                }
            ).encode("utf-8")
        ).decode("ascii")
        headers = {
            "Ocp-Apim-Subscription-Key": self._subscription_key,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Accept": "application/json",
            "Pronunciation-Assessment": pronunciation_config,
        }
        params = {"language": language, "format": "detailed"}
        audio_bytes = audio_path.read_bytes()

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = httpx.post(
                    url,
                    params=params,
                    headers=headers,
                    content=audio_bytes,
                    timeout=self._timeout_seconds,
                )
                response.raise_for_status()
                return _parse_response(response.json())
            except (httpx.HTTPError, LookupError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(_RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)])

        raise AnalysisError(
            code="PRONUNCIATION_PROVIDER_FAILED",
            message=f"Azure 발음평가 호출 실패: {type(last_error).__name__}",
            retryable=True,
        ) from last_error


def _parse_response(data: dict) -> PronunciationAssessment:
    n_best = data.get("NBest") or []
    if not n_best:
        raise ValueError("Azure 응답에 NBest 결과가 없습니다")

    assessment = n_best[0].get("PronunciationAssessment") or {}
    pronunciation_score = assessment.get("PronScore")
    if pronunciation_score is None:
        raise ValueError("Azure 응답에 PronScore가 없습니다")

    fluency_score = assessment.get("FluencyScore")

    return PronunciationAssessment(
        provider="azure",
        pronunciation_score=int(round(pronunciation_score)),
        fluency_score=int(round(fluency_score)) if fluency_score is not None else None,
        raw_response={
            "accuracyScore": assessment.get("AccuracyScore"),
            "completenessScore": assessment.get("CompletenessScore"),
            "fluencyScore": fluency_score,
        },
    )
