from __future__ import annotations

from collections.abc import Callable

from app.application.workers.watchdog import Watchdog
from app.domain.errors import RepositoryTimeoutError


class _FakeJobRepository:
    def __init__(
        self,
        batch_results: list[int],
        on_requeue: Callable[[], None] | None = None,
    ) -> None:
        self._batch_results = iter(batch_results)
        self._on_requeue = on_requeue
        self.batch_sizes: list[int] = []
        self.timeouts: list[float | None] = []

    def requeue_expired_leases(
        self,
        *,
        batch_size: int = 100,
        timeout_seconds: float | None = None,
    ) -> int:
        self.batch_sizes.append(batch_size)
        self.timeouts.append(timeout_seconds)
        if self._on_requeue is not None:
            self._on_requeue()
        return next(self._batch_results)


def _watchdog(
    repository,
    *,
    batch_size: int = 2,
    max_batches: int = 10,
    max_run_seconds: float = 10,
    monotonic=lambda: 0.0,
) -> Watchdog:
    return Watchdog(
        job_repository=repository,
        watchdog_check_interval_seconds=30,
        batch_size=batch_size,
        max_batches_per_cycle=max_batches,
        max_run_seconds=max_run_seconds,
        connection_acquire_timeout_seconds=0.1,
        monotonic=monotonic,
    )


def test_watchdog_processes_multiple_batches_until_queue_is_drained():
    # given
    repository = _FakeJobRepository([2, 2, 1])
    watchdog = _watchdog(repository)

    # when
    result = watchdog.run_cycle()

    # then
    assert result.requeued_jobs == 5
    assert result.processed_batches == 3
    assert result.stop_reason == "queue_drained"
    assert repository.batch_sizes == [2, 2, 2]
    assert repository.timeouts == [10.0, 10.0, 10.0]


def test_watchdog_stops_at_max_batches_per_cycle():
    # given
    repository = _FakeJobRepository([2, 2, 2, 2])
    watchdog = _watchdog(repository, max_batches=3)

    # when
    result = watchdog.run_cycle()

    # then
    assert result.requeued_jobs == 6
    assert result.processed_batches == 3
    assert result.stop_reason == "max_batches"


def test_watchdog_stops_at_max_run_seconds_between_batches():
    # given
    timestamps = iter((0.0, 0.0, 1.1, 1.1))
    repository = _FakeJobRepository([2, 2])
    watchdog = _watchdog(
        repository,
        max_run_seconds=1,
        monotonic=lambda: next(timestamps),
    )

    # when
    result = watchdog.run_cycle()

    # then
    assert result.requeued_jobs == 2
    assert result.processed_batches == 1
    assert result.stop_reason == "max_run_seconds"
    assert repository.timeouts == [1.0]


def test_watchdog_stops_next_batch_when_shutdown_is_requested():
    # given
    repository = _FakeJobRepository([2, 2])
    watchdog = _watchdog(repository)
    repository._on_requeue = watchdog.stop

    # when
    result = watchdog.run_cycle()

    # then
    assert result.requeued_jobs == 2
    assert result.processed_batches == 1
    assert result.stop_reason == "shutdown"


def test_watchdog_stops_cycle_when_database_batch_exhausts_remaining_time():
    # given
    class _TimedOutRepository:
        def requeue_expired_leases(
            self,
            *,
            batch_size: int = 100,
            timeout_seconds: float | None = None,
        ) -> int:
            raise RepositoryTimeoutError("statement timeout")

    watchdog = _watchdog(_TimedOutRepository(), max_run_seconds=3)

    # when
    result = watchdog.run_cycle()

    # then
    assert result.requeued_jobs == 0
    assert result.processed_batches == 0
    assert result.stop_reason == "max_run_seconds"
