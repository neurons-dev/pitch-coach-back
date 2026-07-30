from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.domain.errors import RepositoryTimeoutError
from app.domain.repositories import JobRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WatchdogCycleResult:
    requeued_jobs: int
    processed_batches: int
    elapsed_seconds: float
    stop_reason: str


class Watchdog:
    def __init__(
        self,
        *,
        job_repository: JobRepository,
        watchdog_check_interval_seconds: float,
        batch_size: int,
        max_batches_per_cycle: int,
        max_run_seconds: float,
        connection_acquire_timeout_seconds: float,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if max_batches_per_cycle < 1:
            raise ValueError("max_batches_per_cycle must be at least 1")
        if max_run_seconds <= 0:
            raise ValueError("max_run_seconds must be greater than 0")
        if not 0 < connection_acquire_timeout_seconds < max_run_seconds:
            raise ValueError(
                "connection_acquire_timeout_seconds must be greater than 0 "
                "and shorter than max_run_seconds"
            )

        self._jobs = job_repository
        self._watchdog_check_interval_seconds = watchdog_check_interval_seconds
        self._batch_size = batch_size
        self._max_batches_per_cycle = max_batches_per_cycle
        self._max_run_seconds = max_run_seconds
        self._connection_acquire_timeout_seconds = (
            connection_acquire_timeout_seconds
        )
        self._monotonic = monotonic
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="watchdog", daemon=True)
        self._thread.start()
        logger.info("watchdog started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._max_run_seconds + 1)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                result = self.run_cycle()
                self._log_cycle(result)
            except Exception:
                logger.exception("watchdog loop error")
            self._stop_event.wait(self._watchdog_check_interval_seconds)

    def run_cycle(self) -> WatchdogCycleResult:
        started_at = self._monotonic()
        requeued_jobs = 0
        processed_batches = 0
        stop_reason = "queue_drained"

        while True:
            if self._stop_event.is_set():
                stop_reason = "shutdown"
                break
            if processed_batches >= self._max_batches_per_cycle:
                stop_reason = "max_batches"
                break
            elapsed_seconds = self._monotonic() - started_at
            remaining_seconds = self._max_run_seconds - elapsed_seconds
            if remaining_seconds <= self._connection_acquire_timeout_seconds:
                stop_reason = "max_run_seconds"
                break

            try:
                requeued = self._jobs.requeue_expired_leases(
                    batch_size=self._batch_size,
                    timeout_seconds=remaining_seconds,
                )
            except RepositoryTimeoutError:
                logger.warning("watchdog batch exhausted cycle time budget")
                stop_reason = "max_run_seconds"
                break
            processed_batches += 1
            requeued_jobs += requeued

            if requeued < self._batch_size:
                stop_reason = "queue_drained"
                break

        return WatchdogCycleResult(
            requeued_jobs=requeued_jobs,
            processed_batches=processed_batches,
            elapsed_seconds=max(0.0, self._monotonic() - started_at),
            stop_reason=stop_reason,
        )

    @staticmethod
    def _log_cycle(result: WatchdogCycleResult) -> None:
        if result.stop_reason in {"max_batches", "max_run_seconds"}:
            logger.warning(
                "watchdog cycle reached limit requeued_jobs=%s batches=%s "
                "elapsed_seconds=%.3f stop_reason=%s",
                result.requeued_jobs,
                result.processed_batches,
                result.elapsed_seconds,
                result.stop_reason,
            )
        elif result.requeued_jobs:
            logger.warning(
                "watchdog cycle recovered jobs requeued_jobs=%s batches=%s "
                "elapsed_seconds=%.3f stop_reason=%s",
                result.requeued_jobs,
                result.processed_batches,
                result.elapsed_seconds,
                result.stop_reason,
            )
        else:
            logger.debug(
                "watchdog cycle idle batches=%s elapsed_seconds=%.3f stop_reason=%s",
                result.processed_batches,
                result.elapsed_seconds,
                result.stop_reason,
            )
