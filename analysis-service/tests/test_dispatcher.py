from __future__ import annotations

import time
import uuid

from app.application.workers.dispatcher import Dispatcher
from app.domain.entities import ClaimedJob


class _FakeJobRepository:
    def __init__(self, *, claim: ClaimedJob, renew_result: bool = True) -> None:
        self._claim = claim
        self._claim_given = False
        self._renew_result = renew_result
        self.complete_calls: list[tuple] = []
        self.fail_calls: list[tuple] = []

    def claim_next_job(self, *, lease_duration_seconds):
        if self._claim_given:
            return None
        self._claim_given = True
        return self._claim

    def renew_lease(self, job_id, *, lease_token, lease_duration_seconds) -> bool:
        return self._renew_result

    def complete_job(self, job_id, *, lease_token) -> bool:
        self.complete_calls.append((job_id, lease_token))
        return True

    def fail_job(self, job_id, *, lease_token, code, message, retryable) -> bool:
        self.fail_calls.append((job_id, lease_token, code, message, retryable))
        return True


def _claim() -> ClaimedJob:
    return ClaimedJob(
        id=uuid.uuid4(), audio_object_key="a.m4a", analysis_version="v1", lease_token=uuid.uuid4()
    )


def test_dispatcher_completes_job_when_lease_is_held_throughout():
    claim = _claim()
    fake = _FakeJobRepository(claim=claim)
    dispatcher = Dispatcher(
        job_repository=fake,
        lease_duration_seconds=300,
        worker_poll_interval_seconds=2.0,
        lease_heartbeat_interval_seconds=60.0,
        analysis_runner=lambda **_: None,
    )

    processed = dispatcher._process_next(
        lease_duration_seconds=300, heartbeat_interval_seconds=60
    )

    assert processed is True
    assert fake.complete_calls == [(claim.id, claim.lease_token)]
    assert fake.fail_calls == []


def test_dispatcher_discards_result_when_lease_is_lost_during_analysis():
    claim = _claim()
    # renew_lease always reports failure, simulating the lease already being reassigned.
    fake = _FakeJobRepository(claim=claim, renew_result=False)

    def slow_analysis(**_):
        time.sleep(0.2)

    dispatcher = Dispatcher(
        job_repository=fake,
        lease_duration_seconds=300,
        worker_poll_interval_seconds=2.0,
        lease_heartbeat_interval_seconds=60.0,
        analysis_runner=slow_analysis,
    )

    processed = dispatcher._process_next(
        lease_duration_seconds=300, heartbeat_interval_seconds=0.05
    )

    assert processed is True
    # lease_lost was detected before the result could be saved, so complete_job
    # must never be called with a result that no longer belongs to this worker.
    assert fake.complete_calls == []
