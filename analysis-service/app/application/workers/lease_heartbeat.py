from __future__ import annotations

import logging
import threading
import time
import uuid

from app.domain.repositories import JobRepository

logger = logging.getLogger(__name__)


class LeaseHeartbeat:
    def __init__(
        self,
        *,
        job_repository: JobRepository,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
        lease_duration_seconds: int,
        interval_seconds: float,
    ) -> None:
        self._jobs = job_repository
        self._job_id = job_id
        self._lease_token = lease_token
        self._lease_duration_seconds = lease_duration_seconds
        self._interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._lease_lost_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def lease_lost(self) -> bool:
        return self._lease_lost_event.is_set()

    def __enter__(self) -> LeaseHeartbeat:
        self._thread = threading.Thread(
            target=self._run_loop, name=f"lease-heartbeat-{self._job_id}", daemon=True
        )
        self._thread.start()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run_loop(self) -> None:
        last_renewed_at = time.monotonic()
        while not self._stop_event.wait(self._interval_seconds):
            try:
                renewed = self._jobs.renew_lease(
                    self._job_id,
                    lease_token=self._lease_token,
                    lease_duration_seconds=self._lease_duration_seconds,
                )
            except Exception:
                logger.exception("lease heartbeat failed job=%s", self._job_id)
                if time.monotonic() - last_renewed_at < self._lease_duration_seconds:
                    continue
                self._lease_lost_event.set()
                self._stop_event.set()
                logger.warning(
                    "lease renewal errors persisted past lease window job=%s", self._job_id
                )
                return

            if renewed:
                last_renewed_at = time.monotonic()
                continue

            self._lease_lost_event.set()
            self._stop_event.set()
            logger.warning("lease ownership lost job=%s", self._job_id)
            return
