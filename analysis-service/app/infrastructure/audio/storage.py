from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.domain.audio import DownloadedAudio
from app.domain.errors import AnalysisError
from app.infrastructure.audio.ffmpeg_utils import probe_duration_ms

_EXTENSION_TO_CONTENT_TYPE: dict[str, str] = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
}

class S3AudioStorage:
    def __init__(self, *, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._max_size_bytes = settings.audio_max_size_bytes
        self._max_duration_ms = settings.audio_max_duration_ms
        self._client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            config=Config(
                connect_timeout=settings.audio_download_timeout_seconds,
                read_timeout=settings.audio_download_timeout_seconds,
                retries={"max_attempts": 1},
            ),
        )

    def download(self, object_key: str) -> DownloadedAudio:
        content_type = self._resolve_content_type(object_key)
        tmp_path = Path(tempfile.gettempdir()) / f"analysis-{uuid.uuid4().hex}{Path(object_key).suffix}"

        try:
            self._client.download_file(self._bucket, object_key, str(tmp_path))
        except (BotoCoreError, ClientError) as exc:
            tmp_path.unlink(missing_ok=True)
            raise AnalysisError(
                code="AUDIO_DOWNLOAD_FAILED",
                message=f"S3 오디오 다운로드 실패: {object_key}",
                retryable=True,
            ) from exc

        try:
            return self._validate(tmp_path, object_key, content_type)
        except AnalysisError:
            tmp_path.unlink(missing_ok=True)
            raise

    def _validate(self, tmp_path: Path, object_key: str, content_type: str) -> DownloadedAudio:
        size_bytes = tmp_path.stat().st_size
        if size_bytes == 0:
            raise AnalysisError(
                code="AUDIO_EMPTY",
                message=f"오디오 파일이 비어 있습니다: {object_key}",
                retryable=False,
            )
        if size_bytes > self._max_size_bytes:
            raise AnalysisError(
                code="AUDIO_TOO_LARGE",
                message=f"오디오 파일이 너무 큽니다 ({size_bytes} bytes): {object_key}",
                retryable=False,
            )

        duration_ms = probe_duration_ms(tmp_path)
        if duration_ms > self._max_duration_ms:
            raise AnalysisError(
                code="AUDIO_TOO_LONG",
                message=f"오디오 길이가 너무 깁니다 ({duration_ms}ms): {object_key}",
                retryable=False,
            )

        return DownloadedAudio(
            path=tmp_path,
            content_type=content_type,
            size_bytes=size_bytes,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _resolve_content_type(object_key: str) -> str:
        extension = Path(object_key).suffix.lower()
        content_type = _EXTENSION_TO_CONTENT_TYPE.get(extension)
        if content_type is None:
            raise AnalysisError(
                code="AUDIO_FORMAT_NOT_SUPPORTED",
                message=f"지원하지 않는 오디오 형식입니다: {object_key}",
                retryable=False,
            )
        return content_type
