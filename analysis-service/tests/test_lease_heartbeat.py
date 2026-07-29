from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from app.application.workers.lease_heartbeat import LeaseHeartbeat


class _FakeJobRepository:
    def __init__(self, renew_fn: Callable[[int], bool]) -> None:
        self._renew_fn = renew_fn
        self.calls = 0

    def renew_lease(self, job_id, *, lease_token, lease_duration_seconds) -> bool:
        self.calls += 1
        return self._renew_fn(self.calls)


def test_heartbeat_keeps_lease_alive_while_renewals_succeed():
    fake = _FakeJobRepository(lambda _call: True)
    heartbeat = LeaseHeartbeat(
        job_repository=fake,
        job_id=uuid.uuid4(),
        lease_token=uuid.uuid4(),
        lease_duration_seconds=300,
        interval_seconds=0.05,
    )

    with heartbeat:
        time.sleep(0.2)

    assert heartbeat.lease_lost is False
    assert fake.calls >= 2


def test_heartbeat_detects_lost_lease_when_renew_returns_false():
    fake = _FakeJobRepository(lambda _call: False)
    heartbeat = LeaseHeartbeat(
        job_repository=fake,
        job_id=uuid.uuid4(),
        lease_token=uuid.uuid4(),
        lease_duration_seconds=300,
        interval_seconds=0.05,
    )

    with heartbeat:
        time.sleep(0.2)

    assert heartbeat.lease_lost is True


def test_heartbeat_tolerates_a_transient_db_error_within_the_lease_window():
    def flaky(call: int) -> bool:
        if call == 1:
            raise RuntimeError("transient db error")
        return True

    fake = _FakeJobRepository(flaky)
    heartbeat = LeaseHeartbeat(
        job_repository=fake,
        job_id=uuid.uuid4(),
        lease_token=uuid.uuid4(),
        lease_duration_seconds=300,
        interval_seconds=0.05,
    )

    with heartbeat:
        time.sleep(0.2)

    assert heartbeat.lease_lost is False


def test_heartbeat_gives_up_once_errors_persist_past_the_lease_duration():
    def always_fail(_call: int) -> bool:
        raise RuntimeError("db down")

    fake = _FakeJobRepository(always_fail)
    heartbeat = LeaseHeartbeat(
        job_repository=fake,
        job_id=uuid.uuid4(),
        lease_token=uuid.uuid4(),
        lease_duration_seconds=1,
        interval_seconds=0.1,
    )

    with heartbeat:
        time.sleep(1.5)

    assert heartbeat.lease_lost is True
