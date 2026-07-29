from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from app.application.workers.lease_heartbeat import LeaseHeartbeat
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
        lease_duration_seconds: int,
        worker_poll_interval_seconds: float,
        lease_heartbeat_interval_seconds: float,
        analysis_runner: AnalysisRunner = _stub_run_analysis,
    ) -> None:
        self._jobs = job_repository
        self._lease_duration_seconds = lease_duration_seconds
        self._worker_poll_interval_seconds = worker_poll_interval_seconds
        self._lease_heartbeat_interval_seconds = lease_heartbeat_interval_seconds
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
        while not self._stop_event.is_set():
            try:
                processed = self._process_next(
                    lease_duration_seconds=self._lease_duration_seconds,
                    heartbeat_interval_seconds=self._lease_heartbeat_interval_seconds,
                )
            except Exception:
                logger.exception("dispatcher loop error")
                processed = False
            if not processed:
                self._stop_event.wait(self._worker_poll_interval_seconds)

    def _process_next(
        self, *, lease_duration_seconds: int, heartbeat_interval_seconds: float
    ) -> bool:
        claim = self._jobs.claim_next_job(lease_duration_seconds=lease_duration_seconds)
        if claim is None:
            return False

        logger.info("dispatcher claimed job=%s", claim.id)
        heartbeat_interval = max(0.1, min(heartbeat_interval_seconds, lease_duration_seconds / 3))

        try:
            with LeaseHeartbeat(
                job_repository=self._jobs,
                job_id=claim.id,
                lease_token=claim.lease_token,
                lease_duration_seconds=lease_duration_seconds,
                interval_seconds=heartbeat_interval,
            ) as heartbeat:
                self._analysis_runner(
                    audio_object_key=claim.audio_object_key,
                    analysis_version=claim.analysis_version,
                )
        except AnalysisError as exc:
            owned = self._jobs.fail_job(
                claim.id,
                lease_token=claim.lease_token,
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
            )
            if owned:
                logger.warning("dispatcher job failed job=%s code=%s", claim.id, exc.code)
            else:
                logger.warning("discarded stale failure job=%s code=%s", claim.id, exc.code)
            return True
        except Exception as exc:
            owned = self._jobs.fail_job(
                claim.id,
                lease_token=claim.lease_token,
                code="ANALYSIS_FAILED",
                message=str(exc),
                retryable=True,
            )
            if owned:
                logger.exception("dispatcher unexpected error job=%s", claim.id)
            else:
                logger.warning("discarded stale unexpected failure job=%s", claim.id)
            return True

        if heartbeat.lease_lost:
            logger.warning("discarded result after lease loss job=%s", claim.id)
            return True

        completed = self._jobs.complete_job(claim.id, lease_token=claim.lease_token)
        if completed:
            logger.info("dispatcher completed job=%s", claim.id)
        else:
            logger.warning("discarded stale result job=%s", claim.id)
        return True
