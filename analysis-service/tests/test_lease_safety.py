from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.infrastructure.db.models import AnalysisJob
from app.infrastructure.db.session import transaction_scope


def test_claim_assigns_lease_token(job_repository, make_job):
    job_id = make_job()

    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    assert claim is not None
    assert claim.id == job_id
    assert claim.lease_token is not None


def test_complete_job_rejects_mismatched_lease_token(job_repository, make_job):
    make_job()
    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    accepted = job_repository.complete_job(claim.id, lease_token=uuid.uuid4())

    assert accepted is False
    assert job_repository.get_job(claim.id).status == "processing"


def test_complete_job_succeeds_with_matching_lease_token(job_repository, make_job):
    make_job()
    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    accepted = job_repository.complete_job(claim.id, lease_token=claim.lease_token)

    assert accepted is True
    assert job_repository.get_job(claim.id).status == "completed"


def test_fail_job_rejects_mismatched_lease_token(job_repository, make_job):
    make_job()
    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    accepted = job_repository.fail_job(
        claim.id, lease_token=uuid.uuid4(), code="X", message="x", retryable=False
    )

    assert accepted is False
    assert job_repository.get_job(claim.id).status == "processing"


def test_renew_lease_rejects_mismatched_lease_token(job_repository, make_job):
    make_job()
    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    renewed = job_repository.renew_lease(
        claim.id, lease_token=uuid.uuid4(), lease_duration_seconds=300
    )

    assert renewed is False


def test_renew_lease_succeeds_with_matching_lease_token(job_repository, make_job):
    make_job()
    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    renewed = job_repository.renew_lease(
        claim.id, lease_token=claim.lease_token, lease_duration_seconds=300
    )

    assert renewed is True


def test_stale_worker_cannot_complete_after_watchdog_reassigns_job(job_repository, make_job):
    job_id = make_job()
    claim_a = job_repository.claim_next_job(lease_duration_seconds=300)

    # Worker A's lease expires while it is still (slowly) working.
    with transaction_scope() as session:
        session.execute(
            update(AnalysisJob)
            .where(AnalysisJob.id == job_id)
            .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )

    recovered = job_repository.requeue_expired_leases()
    assert recovered == 1

    claim_b = job_repository.claim_next_job(lease_duration_seconds=300)
    assert claim_b.id == job_id
    assert claim_b.lease_token != claim_a.lease_token

    # Worker A finally finishes and tries to save its (stale) result.
    stale_accepted = job_repository.complete_job(job_id, lease_token=claim_a.lease_token)
    assert stale_accepted is False

    # Worker B, the current owner, completes successfully.
    real_accepted = job_repository.complete_job(job_id, lease_token=claim_b.lease_token)
    assert real_accepted is True
    assert job_repository.get_job(job_id).status == "completed"
