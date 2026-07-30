from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.domain.entities import AnalysisResultInput, FeedbackItemInput, MetricScoreInput
from app.infrastructure.db.models import AnalysisResult


def _result(**overrides) -> AnalysisResultInput:
    values = {
        "overall_score": 88,
        "pipeline_version": "audio-0.1",
        "stt_model_version": "faster-whisper-small",
        "scoring_rule_version": "coach-ko-template-0.1",
        "coach_comment": "Stable overall.",
        "transcript_text": "Hello.",
        "transcript_segments": [{"startMs": 0, "endMs": 1000, "text": "Hello."}],
        "total_speech_ms": 1000,
        "total_silence_ms": 0,
        "model_info": {"provider": "local"},
        "metric_scores": [
            MetricScoreInput(metric_code="SPEED", score=82, raw_value=430, unit="CPM"),
        ],
        "feedback_items": [
            FeedbackItemInput(
                item_type="strength",
                title="Pace",
                description="The pace was stable.",
                metric_code="SPEED",
                sort_order=1,
            ),
        ],
    }
    values.update(overrides)
    return AnalysisResultInput(**values)


def test_save_result_and_complete_persists_result_and_completes_job(
    job_repository, make_job, database_session_provider
):
    # given
    make_job()
    claim = job_repository.claim_next_job(lease_duration_seconds=300)

    # when
    saved = job_repository.save_result_and_complete(
        claim.id, lease_token=claim.lease_token, result=_result()
    )

    # then
    assert saved is True
    job = job_repository.get_job(claim.id)
    assert job.status == "completed"
    assert job.lease_token is None

    with database_session_provider.read_session_scope() as session:
        result = session.scalars(
            select(AnalysisResult)
            .where(AnalysisResult.job_id == claim.id)
            .options(selectinload(AnalysisResult.metric_scores), selectinload(AnalysisResult.feedback_items))
        ).one()
        assert result.overall_score == 88
        assert result.pipeline_version == "audio-0.1"
        assert len(result.metric_scores) == 1
        assert len(result.feedback_items) == 1


def test_save_result_and_complete_rejects_mismatched_lease_token(
    job_repository, make_job, database_session_provider
):
    # given
    job_id = make_job()
    job_repository.claim_next_job(lease_duration_seconds=300)

    # when
    saved = job_repository.save_result_and_complete(
        job_id, lease_token=uuid.uuid4(), result=_result()
    )

    # then
    assert saved is False
    assert job_repository.get_job(job_id).status == "processing"
    with database_session_provider.read_session_scope() as session:
        count = session.scalars(
            select(AnalysisResult).where(AnalysisResult.job_id == job_id)
        ).all()
        assert count == []


def test_save_result_and_complete_rolls_back_job_on_constraint_violation(
    job_repository, make_job, database_session_provider
):
    # given
    job_id = make_job()
    claim = job_repository.claim_next_job(lease_duration_seconds=300)
    invalid_result = _result(
        metric_scores=[
            MetricScoreInput(metric_code="SPEED", score=80),
            MetricScoreInput(metric_code="SPEED", score=90),  # duplicate -> UNIQUE violation
        ]
    )

    # when / then
    with pytest.raises(IntegrityError):
        job_repository.save_result_and_complete(
            claim.id, lease_token=claim.lease_token, result=invalid_result
        )

    # the whole transaction (result insert + job completion) must have rolled back
    assert job_repository.get_job(job_id).status == "processing"
    with database_session_provider.read_session_scope() as session:
        rows = session.scalars(
            select(AnalysisResult).where(AnalysisResult.job_id == job_id)
        ).all()
        assert rows == []
