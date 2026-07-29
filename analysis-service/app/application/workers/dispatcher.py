from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from app.core.config import get_settings
from app.domain.errors import AnalysisError
from app.domain.repositories import JobRepository

logger = logging.getLogger(__name__)

AnalysisRunner = Callable[..., None]


def _stub_run_analysis(*, audio_object_key: str, analysis_version: str) -> None:
    """실제 분석 파이프라인이 아직 없어 큐 동작만 검증하는 임시 구현."""
    time.sleep(0.1)


class Dispatcher:
    def __init__(
        self,
        *,
        job_repository: JobRepository,
        analysis_runner: AnalysisRunner = _stub_run_analysis,
    ) -> None:
        self._jobs = job_repository
        self._analysis_runner = analysis_runner
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="dispatcher", daemon=True)
        self._thread.start()
        logger.info("dispatcher started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run_loop(self) -> None:
        settings = get_settings()
        while not self._stop_event.is_set():
            try:
                processed = self._process_next(settings.lease_duration_seconds)
            except Exception:
                logger.exception("dispatcher loop error")
                processed = False
            if not processed:
                self._stop_event.wait(settings.worker_poll_interval_seconds)

    def _process_next(self, lease_duration_seconds: int) -> bool:
        job = self._jobs.claim_next_job(lease_duration_seconds=lease_duration_seconds)
        if job is None:
            return False

        logger.info("dispatcher claimed job=%s", job.id)

        try:
            self._analysis_runner(
                audio_object_key=job.audio_object_key, analysis_version=job.analysis_version
            )
        except AnalysisError as exc:
            self._jobs.fail_job(job.id, code=exc.code, message=exc.message, retryable=exc.retryable)
            logger.warning("dispatcher job failed job=%s code=%s", job.id, exc.code)
            return True
        except Exception as exc:
            self._jobs.fail_job(job.id, code="ANALYSIS_FAILED", message=str(exc), retryable=True)
            logger.exception("dispatcher unexpected error job=%s", job.id)
            return True

        self._jobs.complete_job(job.id)
        logger.info("dispatcher completed job=%s", job.id)
        return True
