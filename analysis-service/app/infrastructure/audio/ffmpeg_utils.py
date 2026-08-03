from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.domain.errors import AnalysisError

_PROBE_TIMEOUT_SECONDS = 30


def probe_duration_ms(path: Path) -> int:
    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AnalysisError(
            code="AUDIO_FORMAT_NOT_SUPPORTED",
            message=f"오디오 길이를 확인할 수 없습니다: {path.name}",
            retryable=False,
        ) from exc

    if completed.returncode != 0:
        raise AnalysisError(
            code="AUDIO_FORMAT_NOT_SUPPORTED",
            message=f"오디오 길이를 확인할 수 없습니다: {path.name}",
            retryable=False,
        )

    try:
        duration_seconds = float(json.loads(completed.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise AnalysisError(
            code="AUDIO_FORMAT_NOT_SUPPORTED",
            message=f"오디오 길이를 확인할 수 없습니다: {path.name}",
            retryable=False,
        ) from exc

    return int(duration_seconds * 1000)
