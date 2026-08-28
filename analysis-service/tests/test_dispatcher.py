from __future__ import annotations

import time
import uuid

from app.application.workers.dispatcher import Dispatcher
from app.domain.entities import AnalysisResultInput, ClaimedJob


class _FakeJobRepository:
    def __init__(self, *, claim: ClaimedJob, renew_result: bool = True) -> None:
        self._claim = claim
        self._claim_given = False
        self._renew_result = renew_result
        self.save_result_calls: list[tuple] = []
        self.fail_calls: list[tuple] = []
        self.progress_calls: list[tuple] = []

    def claim_next_job(self, *, lease_duration_seconds):
        if self._claim_given:
            return None
        self._claim_given = True
        return self._claim

    def renew_lease(self, job_id, *, lease_token, lease_duration_seconds) -> bool:
        return self._renew_result

    def update_progress(self, job_id, *, lease_token, stage, progress_percent) -> bool:
        self.progress_calls.append((job_id, lease_token, stage, progress_percent))
        return True

    def save_result_and_complete(self, job_id, *, lease_token, result) -> bool:
        self.save_result_calls.append((job_id, lease_token, result))
        return True

    def fail_job(self, job_id, *, lease_token, code, message, retryable) -> bool:
        self.fail_calls.append((job_id, lease_token, code, message, retryable))
        return True


def _claim() -> ClaimedJob:
    return ClaimedJob(
        id=uuid.uuid4(), audio_object_key="a.m4a", analysis_version="v1", lease_token=uuid.uuid4()
    )


def _result() -> AnalysisResultInput:
    return AnalysisResultInput(
        overall_score=80,
        pipeline_version="audio-pipeline-v1",
        stt_model_version="faster-whisper-tiny",
        scoring_rule_version="coach-ko-v1",
    )


def test_dispatcher_completes_job_when_lease_is_held_throughout():
    claim = _claim()
    fake = _FakeJobRepository(claim=claim)
    boundary_events: list[str] = []
    result = _result()
    dispatcher = Dispatcher(
        job_repository=fake,
        lease_duration_seconds=300,
        worker_poll_interval_seconds=2.0,
        lease_heartbeat_interval_seconds=60.0,
        analysis_runner=lambda **_: result,
        analysis_boundary_observer=boundary_events.append,
    )

    processed = dispatcher._process_next(
        lease_duration_seconds=300, heartbeat_interval_seconds=60
    )

    assert processed is True
    assert fake.save_result_calls == [(claim.id, claim.lease_token, result)]
    assert fake.fail_calls == []
    assert boundary_events == ["before_analysis", "after_analysis"]


def test_dispatcher_passes_presentation_context_to_analysis_runner():
    # given
    claim = ClaimedJob(
        id=uuid.uuid4(),
        audio_object_key="a.m4a",
        analysis_version="v1",
        lease_token=uuid.uuid4(),
        presentation_title="면접 발표 연습",
        practice_type_code="INTERVIEW",
    )
    fake = _FakeJobRepository(claim=claim)
    received: dict = {}

    def run_analysis(**kwargs):
        received.update(kwargs)
        return _result()

    dispatcher = Dispatcher(
        job_repository=fake,
        lease_duration_seconds=300,
        worker_poll_interval_seconds=2.0,
        lease_heartbeat_interval_seconds=60.0,
        analysis_runner=run_analysis,
    )

    # when
    dispatcher._process_next(lease_duration_seconds=300, heartbeat_interval_seconds=60)

    # then
    assert received["presentation_title"] == "면접 발표 연습"
    assert received["practice_type_code"] == "INTERVIEW"


def test_dispatcher_gives_runner_a_lease_guarded_progress_reporter():
    # given
    claim = _claim()
    fake = _FakeJobRepository(claim=claim)

    def run_analysis(*, progress_reporter, **_):
        progress_reporter("TRANSCRIBING", 35)
        progress_reporter("GENERATING_FEEDBACK", 85)
        return _result()

    dispatcher = Dispatcher(
        job_repository=fake,
        lease_duration_seconds=300,
        worker_poll_interval_seconds=2.0,
        lease_heartbeat_interval_seconds=60.0,
        analysis_runner=run_analysis,
    )

    # when
    dispatcher._process_next(lease_duration_seconds=300, heartbeat_interval_seconds=60)

    # then
    assert fake.progress_calls == [
        (claim.id, claim.lease_token, "TRANSCRIBING", 35),
        (claim.id, claim.lease_token, "GENERATING_FEEDBACK", 85),
    ]


def test_dispatcher_discards_result_when_lease_is_lost_during_analysis():
    claim = _claim()
    fake = _FakeJobRepository(claim=claim, renew_result=False)

    def slow_analysis(**_):
        time.sleep(0.2)
        return _result()

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
    assert fake.save_result_calls == []


def test_dispatcher_fails_job_when_analysis_raises():
    from app.domain.errors import AnalysisError

    claim = _claim()
    fake = _FakeJobRepository(claim=claim)

    def failing_analysis(**_):
        raise AnalysisError(code="AUDIO_DOWNLOAD_FAILED", message="boom", retryable=True)

    dispatcher = Dispatcher(
        job_repository=fake,
        lease_duration_seconds=300,
        worker_poll_interval_seconds=2.0,
        lease_heartbeat_interval_seconds=60.0,
        analysis_runner=failing_analysis,
    )

    processed = dispatcher._process_next(
        lease_duration_seconds=300, heartbeat_interval_seconds=60
    )

    assert processed is True
    assert fake.save_result_calls == []
    assert fake.fail_calls == [
        (claim.id, claim.lease_token, "AUDIO_DOWNLOAD_FAILED", "boom", True)
    ]
