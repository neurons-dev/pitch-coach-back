from __future__ import annotations

import logging
import threading

from app.core.config import get_settings
from app.domain.repositories import JobRepository

logger = logging.getLogger(__name__)


class Watchdog:
    def __init__(self, *, job_repository: JobRepository) -> None:
        self._jobs = job_repository
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
            self._thread.join(timeout=5)

    def _run_loop(self) -> None:
        settings = get_settings()
        while not self._stop_event.is_set():
            try:
                requeued = self._jobs.requeue_expired_leases()
                if requeued:
                    logger.warning("watchdog requeued %s stuck job(s)", requeued)
            except Exception:
                logger.exception("watchdog loop error")
            self._stop_event.wait(settings.watchdog_check_interval_seconds)
