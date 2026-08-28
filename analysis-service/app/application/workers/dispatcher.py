from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from app.application.workers.lease_heartbeat import LeaseHeartbeat
from app.domain.entities import AnalysisResultInput, ClaimedJob
from app.domain.errors import AnalysisError
from app.domain.repositories import JobRepository

logger = logging.getLogger(__name__)

_IDLE_LOG_INTERVAL_SECONDS = 60.0

AnalysisRunner = Callable[..., AnalysisResultInput]
AnalysisBoundaryObserver = Callable[[str], None]


class Dispatcher:
    def __init__(
        self,
        *,
        job_repository: JobRepository,
        lease_duration_seconds: int,
        worker_poll_interval_seconds: float,
        lease_heartbeat_interval_seconds: float,
        analysis_runner: AnalysisRunner,
        analysis_boundary_observer: AnalysisBoundaryObserver | None = None,
    ) -> None:
        self._jobs = job_repository
        self._lease_duration_seconds = lease_duration_seconds
        self._worker_poll_interval_seconds = worker_poll_interval_seconds
        self._lease_heartbeat_interval_seconds = lease_heartbeat_interval_seconds
        self._analysis_runner = analysis_runner
        self._analysis_boundary_observer = analysis_boundary_observer
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
        # 유휴 상태를 주기적으로 남긴다. 이 로그가 없으면 "워커가 살아서 폴링 중인데
        # 큐가 비어 있음"과 "워커가 죽어 있음"을 로그만 보고 구분할 수 없다.
        last_idle_log_at = 0.0
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
                now = time.monotonic()
                if now - last_idle_log_at >= _IDLE_LOG_INTERVAL_SECONDS:
                    logger.info("dispatcher idle, no queued job to claim")
                    last_idle_log_at = now
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
            self._observe_analysis_boundary("before_analysis")
            try:
                with LeaseHeartbeat(
                    job_repository=self._jobs,
                    job_id=claim.id,
                    lease_token=claim.lease_token,
                    lease_duration_seconds=lease_duration_seconds,
                    interval_seconds=heartbeat_interval,
                ) as heartbeat:
                    result = self._analysis_runner(
                        audio_object_key=claim.audio_object_key,
                        analysis_version=claim.analysis_version,
                        presentation_title=claim.presentation_title,
                        practice_type_code=claim.practice_type_code,
                        target_duration_sec=claim.target_duration_sec,
                        progress_reporter=self._build_progress_reporter(claim),
                    )
            finally:
                self._observe_analysis_boundary("after_analysis")
        except AnalysisError as exc:
            owned = self._jobs.fail_job(
                claim.id,
                lease_token=claim.lease_token,
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
            )
            if owned:
                logger.warning(
                    "dispatcher job failed job=%s code=%s retryable=%s message=%s",
                    claim.id,
                    exc.code,
                    exc.retryable,
                    exc.message,
                    exc_info=True,
                )
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

        saved = self._jobs.save_result_and_complete(
            claim.id, lease_token=claim.lease_token, result=result
        )
        if saved:
            logger.info("dispatcher completed job=%s score=%s", claim.id, result.overall_score)
        else:
            logger.warning("discarded stale result job=%s", claim.id)
        return True

    def _build_progress_reporter(self, claim: ClaimedJob) -> Callable[[str, int], None]:
        def report(stage: str, progress_percent: int) -> None:
            self._jobs.update_progress(
                claim.id,
                lease_token=claim.lease_token,
                stage=stage,
                progress_percent=progress_percent,
            )

        return report

    def _observe_analysis_boundary(self, event: str) -> None:
        if self._analysis_boundary_observer is None:
            return
        try:
            self._analysis_boundary_observer(event)
        except Exception:
            logger.exception("analysis boundary observer failed event=%s", event)
