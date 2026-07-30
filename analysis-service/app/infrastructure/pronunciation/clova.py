from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from app.domain.entities import MetricCalculationInput, PronunciationAssessment
from app.domain.errors import AnalysisError
from app.infrastructure.audio.ffmpeg_utils import probe_duration_ms

_RETRY_BACKOFF_SECONDS = (0.5, 1.5)
_SPLIT_TIMEOUT_SECONDS = 120


class ClovaPronunciationAssessor:
    def __init__(
        self,
        *,
        invoke_url: str,
        secret_key: str,
        timeout_seconds: float,
        max_chunk_seconds: int,
        max_retries: int = 2,
    ) -> None:
        self._invoke_url = invoke_url
        self._secret_key = secret_key
        self._timeout_seconds = timeout_seconds
        self._max_chunk_seconds = max_chunk_seconds
        self._max_retries = max_retries

    def assess(
        self, *, audio_path: Path, calc_input: MetricCalculationInput, language: str
    ) -> PronunciationAssessment:
        chunk_paths = self._split_if_needed(audio_path)
        try:
            pronunciation_scored: list[tuple[int, int]] = []
            fluency_scored: list[tuple[int, int]] = []
            for chunk_path in chunk_paths:
                duration_ms = probe_duration_ms(chunk_path)
                data = self._call_api(chunk_path, language=language)

                score = data.get("pronunciationScore")
                if score is None:
                    raise ValueError("CLOVA 응답에 pronunciationScore가 없습니다")
                pronunciation_scored.append((int(round(score)), duration_ms))

                fluency = data.get("fluencyScore")
                if fluency is not None:
                    fluency_scored.append((int(round(fluency)), duration_ms))
        finally:
            self._cleanup_chunks(audio_path, chunk_paths)

        return PronunciationAssessment(
            provider="clova",
            pronunciation_score=_weighted_average(pronunciation_scored),
            fluency_score=_weighted_average(fluency_scored) if fluency_scored else None,
            raw_response={"chunkCount": len(chunk_paths)},
        )

    def _split_if_needed(self, audio_path: Path) -> list[Path]:
        duration_ms = probe_duration_ms(audio_path)
        if duration_ms <= self._max_chunk_seconds * 1000:
            return [audio_path]

        output_dir = Path(tempfile.mkdtemp(prefix="clova-chunks-"))
        pattern = output_dir / "chunk_%03d.wav"
        completed = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(audio_path),
                "-f", "segment",
                "-segment_time", str(self._max_chunk_seconds),
                "-c", "copy",
                str(pattern),
            ],
            capture_output=True,
            text=True,
            timeout=_SPLIT_TIMEOUT_SECONDS,
        )
        chunks = sorted(output_dir.glob("chunk_*.wav"))
        if completed.returncode != 0 or not chunks:
            for chunk in chunks:
                chunk.unlink(missing_ok=True)
            output_dir.rmdir()
            raise AnalysisError(
                code="PRONUNCIATION_PROVIDER_FAILED",
                message="CLOVA용 장시간 오디오 분할 실패",
                retryable=False,
            )
        return chunks

    def _cleanup_chunks(self, audio_path: Path, chunk_paths: list[Path]) -> None:
        if chunk_paths == [audio_path]:
            return
        chunk_dir = chunk_paths[0].parent
        for chunk_path in chunk_paths:
            chunk_path.unlink(missing_ok=True)
        try:
            chunk_dir.rmdir()
        except OSError:
            pass

    def _call_api(self, chunk_path: Path, *, language: str) -> dict:
        headers = {
            "X-CLOVASPEECH-API-KEY": self._secret_key,
            "Content-Type": "application/octet-stream",
        }
        params = {"lang": language}
        audio_bytes = chunk_path.read_bytes()

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = httpx.post(
                    self._invoke_url,
                    params=params,
                    headers=headers,
                    content=audio_bytes,
                    timeout=self._timeout_seconds,
                )
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(_RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)])

        raise AnalysisError(
            code="PRONUNCIATION_PROVIDER_FAILED",
            message=f"CLOVA 발음평가 호출 실패: {type(last_error).__name__}",
            retryable=True,
        ) from last_error


def _weighted_average(scored: list[tuple[int, int]]) -> int:
    total_weight = sum(duration for _, duration in scored)
    if total_weight <= 0:
        return int(round(sum(score for score, _ in scored) / len(scored)))
    weighted_sum = sum(score * duration for score, duration in scored)
    return int(round(weighted_sum / total_weight))
