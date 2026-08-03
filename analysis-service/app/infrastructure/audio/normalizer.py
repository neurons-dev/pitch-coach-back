from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from app.domain.errors import AnalysisError

_TARGET_SAMPLE_RATE_HZ = 16000
_TARGET_CHANNELS = 1
_NORMALIZE_TIMEOUT_SECONDS = 120


class FfmpegAudioNormalizer:
    def normalize(self, input_path: Path) -> Path:
        output_path = input_path.with_name(f"{input_path.stem}-norm-{uuid.uuid4().hex[:8]}.wav")

        try:
            completed = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(input_path),
                    "-ac",
                    str(_TARGET_CHANNELS),
                    "-ar",
                    str(_TARGET_SAMPLE_RATE_HZ),
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                timeout=_NORMALIZE_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            output_path.unlink(missing_ok=True)
            raise AnalysisError(
                code="AUDIO_NORMALIZATION_FAILED",
                message=f"오디오 정규화 실패: {input_path.name}",
                retryable=False,
            ) from exc

        if completed.returncode != 0 or not output_path.exists():
            output_path.unlink(missing_ok=True)
            detail = completed.stderr[-500:] if completed.stderr else "unknown ffmpeg error"
            raise AnalysisError(
                code="AUDIO_NORMALIZATION_FAILED",
                message=f"오디오 정규화 실패: {detail}",
                retryable=False,
            )

        if output_path.stat().st_size == 0:
            output_path.unlink(missing_ok=True)
            raise AnalysisError(
                code="AUDIO_NORMALIZATION_FAILED",
                message="정규화된 오디오 파일이 비어 있습니다.",
                retryable=False,
            )

        return output_path
