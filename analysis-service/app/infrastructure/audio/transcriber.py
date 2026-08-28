from __future__ import annotations

import concurrent.futures
import logging
from pathlib import Path

from faster_whisper import WhisperModel

from app.core.config import Settings
from app.domain.audio import Transcript, TranscriptSegment, TranscriptWord
from app.domain.errors import AnalysisError

logger = logging.getLogger(__name__)

# CPU int8 추론은 실시간보다 느릴 수 있어, 고정 타임아웃이면 긴 오디오는 무조건 걸린다.
# 발음 평가와 같은 방식으로 오디오 길이에 비례해 예산을 잡는다.
_TIMEOUT_MULTIPLIER = 3.0
_MIN_TIMEOUT_BUFFER_SECONDS = 30.0


class FasterWhisperTranscriber:
    def __init__(self, *, settings: Settings) -> None:
        self._model_size = settings.whisper_model_size
        self._device = settings.whisper_device
        self._compute_type = settings.whisper_compute_type
        self._timeout_seconds = settings.stt_timeout_seconds
        self._model: WhisperModel | None = None

    def preload(self) -> None:
        """모델을 미리 내려받아 메모리에 올린다.

        기본적으로 모델 로드는 첫 전사 요청 안에서 일어나는데, 그 시간이 STT
        타임아웃 예산에 그대로 포함된다. 캐시가 비어 있으면 수백 MB 다운로드가
        타임아웃을 밀어내 첫 분석이 통째로 실패한다. 워커 기동 시 미리 끝낸다.
        """
        logger.info("whisper 모델 로드 시작 size=%s device=%s", self._model_size, self._device)
        self._get_model()
        logger.info("whisper 모델 로드 완료 size=%s", self._model_size)

    @property
    def model_version(self) -> str:
        return f"faster-whisper-{self._model_size}"

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
        return self._model

    def transcribe(self, audio_path: Path, *, language: str, duration_ms: int) -> Transcript:
        timeout_seconds = max(
            self._timeout_seconds,
            (duration_ms / 1000) * _TIMEOUT_MULTIPLIER + _MIN_TIMEOUT_BUFFER_SECONDS,
        )
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._run_transcribe, audio_path, language)
        try:
            result = future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            executor.shutdown(wait=False)
            raise AnalysisError(
                code="STT_TIMEOUT",
                message=f"STT 처리 시간 초과: {audio_path.name}",
                retryable=True,
            ) from exc
        else:
            executor.shutdown(wait=False)
            return result

    def _run_transcribe(self, audio_path: Path, language: str) -> Transcript:
        model = self._get_model()
        lang_code = language.split("-")[0] if language else None

        try:
            segments_iter, info = model.transcribe(
                str(audio_path),
                language=lang_code,
                vad_filter=True,
                word_timestamps=True,
            )
            segments = [
                TranscriptSegment(
                    start_ms=int(segment.start * 1000),
                    end_ms=int(segment.end * 1000),
                    text=segment.text.strip(),
                    avg_logprob=float(segment.avg_logprob),
                    words=[
                        TranscriptWord(
                            start_ms=int(word.start * 1000),
                            end_ms=int(word.end * 1000),
                            text=word.word.strip(),
                            probability=float(word.probability),
                        )
                        for word in (getattr(segment, "words", None) or [])
                        if word.word.strip()
                    ],
                )
                for segment in segments_iter
            ]
        except Exception as exc:
            raise AnalysisError(
                code="STT_FAILED",
                message=f"STT 처리 실패: {exc}",
                retryable=True,
            ) from exc

        text = " ".join(segment.text for segment in segments if segment.text).strip()
        duration_ms = (
            int(info.duration * 1000)
            if info is not None and getattr(info, "duration", None)
            else (segments[-1].end_ms if segments else 0)
        )

        return Transcript(
            text=text,
            language=lang_code or "unknown",
            model_version=self.model_version,
            duration_ms=duration_ms,
            segments=segments,
        )
