from __future__ import annotations

from types import SimpleNamespace

from app.domain.entities import AnalysisResultInput, FeedbackItemInput, MetricScoreInput
from app.interface.api.jobs import _to_status_response


def _result(**overrides) -> AnalysisResultInput:
    values = {
        "overall_score": 88,
        "pipeline_version": "audio-pipeline-v1",
        "stt_model_version": "faster-whisper-tiny",
        "scoring_rule_version": "coach-ko-v1",
        "coach_comment": "Stable overall.",
        "metric_scores": [
            MetricScoreInput(metric_code="SPEED", score=82, raw_value=430, unit="CPM"),
            MetricScoreInput(metric_code="FILLER", score=95),
        ],
        "feedback_items": [
            FeedbackItemInput(
                item_type="summary",
                title="종합 총평",
                description="Stable overall.",
                metric_code=None,
                sort_order=0,
            ),
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


class TestGetJobEagerLoadsResult:
    def test_completed_job_returns_result_with_metrics_and_feedback(
        self, job_repository, make_job
    ):
        job_id = make_job()
        claim = job_repository.claim_next_job(lease_duration_seconds=300)
        job_repository.save_result_and_complete(
            claim.id, lease_token=claim.lease_token, result=_result()
        )

        job = job_repository.get_job(job_id)

        assert job.status == "completed"
        assert job.result is not None
        assert job.result.overall_score == 88
        assert job.result.coach_comment == "Stable overall."
        assert {m.metric_code for m in job.result.metric_scores} == {"SPEED", "FILLER"}
        assert {f.title for f in job.result.feedback_items} == {"종합 총평", "Pace"}

    def test_in_progress_job_has_no_result(self, job_repository, make_job):
        job_id = make_job()
        job_repository.claim_next_job(lease_duration_seconds=300)

        job = job_repository.get_job(job_id)

        assert job.status == "processing"
        assert job.result is None

    def test_queued_job_has_no_result(self, job_repository, make_job):
        job_id = make_job()

        job = job_repository.get_job(job_id)

        assert job.status == "queued"
        assert job.result is None


def _fake_job(*, status: str, result=None):
    return SimpleNamespace(
        id="00000000-0000-0000-0000-000000000000",
        status=status,
        current_stage="DONE" if status == "completed" else "ANALYZING",
        progress_percent=100 if status == "completed" else 40,
        error_code=None,
        error_message=None,
        result=result,
    )


def _fake_result_like(result_input: AnalysisResultInput):
    return SimpleNamespace(
        overall_score=result_input.overall_score,
        coach_comment=result_input.coach_comment,
        metric_scores=[
            SimpleNamespace(
                metric_code=m.metric_code, score=m.score, raw_value=m.raw_value, unit=m.unit
            )
            for m in result_input.metric_scores
        ],
        feedback_items=[
            SimpleNamespace(
                item_type=f.item_type,
                title=f.title,
                description=f.description,
                metric_code=f.metric_code,
                sort_order=f.sort_order,
            )
            for f in result_input.feedback_items
        ],
    )


class TestToStatusResponseMapping:
    def test_completed_job_maps_full_result(self):
        job = _fake_job(status="completed", result=_fake_result_like(_result()))

        response = _to_status_response(job)

        assert response.result is not None
        assert response.result.overall_score == 88
        assert response.result.coach_comment == "Stable overall."
        assert len(response.result.metric_scores) == 2
        assert len(response.result.feedback_items) == 2
        payload = response.model_dump(by_alias=True)
        assert payload["result"]["metricScores"][0]["metricCode"] == "SPEED"
        assert payload["result"]["feedbackItems"][0]["itemType"] == "summary"

    def test_non_completed_job_returns_null_result(self):
        job = _fake_job(status="processing", result=None)

        response = _to_status_response(job)

        assert response.result is None
        payload = response.model_dump(by_alias=True)
        assert payload["result"] is None
