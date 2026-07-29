from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.infrastructure.db.models import AnalysisJob
from app.infrastructure.db.session import transaction_scope


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


def test_stale_worker_cannot_complete_after_watchdog_reassigns_job(job_repository, make_job):
    # given
    job_id = make_job()
    claim_a = job_repository.claim_next_job(lease_duration_seconds=300)

    with transaction_scope() as session:
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
