from __future__ import annotations

import concurrent.futures
from pathlib import Path

from faster_whisper import WhisperModel

from app.core.config import Settings
from app.domain.audio import Transcript, TranscriptSegment
from app.domain.errors import AnalysisError


class FasterWhisperTranscriber:
    def __init__(self, *, settings: Settings) -> None:
        self._model_size = settings.whisper_model_size
        self._device = settings.whisper_device
        self._compute_type = settings.whisper_compute_type
        self._timeout_seconds = settings.stt_timeout_seconds
        self._model: WhisperModel | None = None

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

    def transcribe(self, audio_path: Path, *, language: str) -> Transcript:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._run_transcribe, audio_path, language)
        try:
            result = future.result(timeout=self._timeout_seconds)
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
                str(audio_path), language=lang_code, vad_filter=True
            )
            segments = [
                TranscriptSegment(
                    start_ms=int(segment.start * 1000),
                    end_ms=int(segment.end * 1000),
                    text=segment.text.strip(),
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
