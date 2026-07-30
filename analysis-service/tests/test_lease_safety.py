from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.application.workers.watchdog import Watchdog
from app.infrastructure.db.models import AnalysisJob


def test_claim_assigns_lease_token(job_repository, make_job):
    # given
    job_id = make_job()

    # when
    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    # then
    assert claim is not None
    assert claim.id == job_id
    assert claim.lease_token is not None


def test_complete_job_rejects_mismatched_lease_token(job_repository, make_job):
    # given
    make_job()
    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    # when
    accepted = job_repository.complete_job(claim.id, lease_token=uuid.uuid4())

    # then
    assert accepted is False
    assert job_repository.get_job(claim.id).status == "processing"


def test_complete_job_succeeds_with_matching_lease_token(job_repository, make_job):
    # given
    make_job()
    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    # when
    accepted = job_repository.complete_job(claim.id, lease_token=claim.lease_token)

    # then
    assert accepted is True
    assert job_repository.get_job(claim.id).status == "completed"


def test_fail_job_rejects_mismatched_lease_token(job_repository, make_job):
    # given
    make_job()
    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    # when
    accepted = job_repository.fail_job(
        claim.id, lease_token=uuid.uuid4(), code="X", message="x", retryable=False
    )

    # then
    assert accepted is False
    assert job_repository.get_job(claim.id).status == "processing"


def test_renew_lease_rejects_mismatched_lease_token(job_repository, make_job):
    # given
    make_job()
    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    # when
    renewed = job_repository.renew_lease(
        claim.id, lease_token=uuid.uuid4(), lease_duration_seconds=300
    )

    # then
    assert renewed is False


def test_renew_lease_succeeds_with_matching_lease_token(job_repository, make_job):
    # given
    make_job()
    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    # when
    renewed = job_repository.renew_lease(
        claim.id, lease_token=claim.lease_token, lease_duration_seconds=300
    )

    # then
    assert renewed is True


def test_stale_worker_cannot_complete_after_watchdog_reassigns_job(
    job_repository,
    make_job,
    database_session_provider,
):
    # given
    job_id = make_job()
    claim_a = job_repository.claim_next_job(lease_duration_seconds=300)

    with database_session_provider.transaction_scope() as session:
        session.execute(
            update(AnalysisJob)
            .where(AnalysisJob.id == job_id)
            .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )

    # when
    recovered = job_repository.requeue_expired_leases()
    claim_b = job_repository.claim_next_job(lease_duration_seconds=300)
    stale_accepted = job_repository.complete_job(job_id, lease_token=claim_a.lease_token)
    real_accepted = job_repository.complete_job(job_id, lease_token=claim_b.lease_token)

    # then
    assert recovered == 1
    assert claim_b.id == job_id
    assert claim_b.lease_token != claim_a.lease_token
    assert stale_accepted is False
    assert real_accepted is True
    assert job_repository.get_job(job_id).status == "completed"


def test_watchdog_requeues_expired_jobs_across_multiple_database_batches(
    job_repository,
    make_job,
    database_session_provider,
):
    # given
    job_ids = [make_job() for _ in range(3)]
    for _ in job_ids:
        job_repository.claim_next_job(lease_duration_seconds=300)

    with database_session_provider.transaction_scope() as session:
        session.execute(
            update(AnalysisJob)
            .where(AnalysisJob.id.in_(job_ids))
            .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )

    watchdog = Watchdog(
        job_repository=job_repository,
        watchdog_check_interval_seconds=30,
        batch_size=2,
        max_batches_per_cycle=5,
        max_run_seconds=10,
        connection_acquire_timeout_seconds=5,
    )

    # when
    result = watchdog.run_cycle()

    # then
    assert result.requeued_jobs == 3
    assert result.processed_batches == 2
    assert result.stop_reason == "queue_drained"
    assert all(job_repository.get_job(job_id).status == "queued" for job_id in job_ids)
