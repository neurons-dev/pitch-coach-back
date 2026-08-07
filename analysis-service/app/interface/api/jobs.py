from __future__ import annotations

import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, Header, Response

from app.core.config import get_settings
from app.domain.entities import AnalysisJobLike
from app.domain.errors import IdempotencyKeyConflictError
from app.domain.repositories import JobRepository
from app.interface.dependencies import get_job_repository
from app.interface.exceptions import ApiException
from app.interface.schemas.errors import ErrorResponse
from app.interface.schemas.jobs import (
    AnalysisJobCreateRequest,
    AnalysisJobCreateResponse,
    AnalysisJobStatusResponse,
    AnalysisResultOut,
    FeedbackItemOut,
    MetricScoreOut,
)

router = APIRouter(
    prefix="/internal/v1/analysis-jobs",
    tags=["analysis-jobs"],
    responses={
        401: {"model": ErrorResponse, "description": "Invalid internal token"},
        422: {"model": ErrorResponse, "description": "Request validation failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
logger = logging.getLogger(__name__)


def _check_token(x_internal_token: str) -> None:
    settings = get_settings()
    if not secrets.compare_digest(x_internal_token, settings.internal_token):
        raise ApiException(
            status_code=401,
            code="INVALID_INTERNAL_TOKEN",
            message="Invalid internal token.",
        )


@router.post(
    "",
    status_code=202,
    responses={
        409: {"model": ErrorResponse, "description": "Idempotency key conflict"},
    },
)
def create_analysis_job(
    body: AnalysisJobCreateRequest,
    response: Response,
    x_internal_token: str = Header(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=100),
    job_repository: JobRepository = Depends(get_job_repository),
) -> AnalysisJobCreateResponse:
    _check_token(x_internal_token)

    try:
        creation = job_repository.create_job(
            idempotency_key=idempotency_key,
            session_id=body.session_id,
            user_id=body.user_id,
            audio_object_key=body.audio_object_key,
            audio_content_type=body.audio_content_type,
            audio_size_bytes=body.audio_size_bytes,
            duration_ms=body.duration_ms,
            presentation_title=body.title,
            practice_type_code=body.practice_type_code,
        )
    except IdempotencyKeyConflictError as exc:
        raise ApiException(
            status_code=409,
            code="IDEMPOTENCY_KEY_CONFLICT",
            message="The idempotency key was already used with a different request.",
        ) from exc

    job_id, status = creation.job.id, creation.job.status

    if creation.created:
        logger.info("analysis-job created job=%s session=%s", job_id, body.session_id)
    else:
        response.status_code = 200
        logger.info(
            "analysis-job reused job=%s disposition=%s", job_id, creation.disposition.value
        )

    response.headers["Location"] = f"/internal/v1/analysis-jobs/{job_id}"
    return AnalysisJobCreateResponse(analysis_job_id=job_id, status=status)


@router.get(
    "/{job_id}",
    responses={
        404: {"model": ErrorResponse, "description": "Analysis job not found"},
    },
)
def get_analysis_job(
    job_id: uuid.UUID,
    x_internal_token: str = Header(...),
    job_repository: JobRepository = Depends(get_job_repository),
) -> AnalysisJobStatusResponse:
    _check_token(x_internal_token)

    job = job_repository.get_job(job_id)
    if job is None:
        raise ApiException(
            status_code=404,
            code="ANALYSIS_JOB_NOT_FOUND",
            message="Analysis job not found.",
        )
    return _to_status_response(job)


def _to_status_response(job: AnalysisJobLike) -> AnalysisJobStatusResponse:
    result_out = None
    if job.result is not None:
        result_out = AnalysisResultOut(
            overall_score=job.result.overall_score,
            coach_comment=job.result.coach_comment,
            metric_scores=[
                MetricScoreOut(
                    metric_code=metric.metric_code,
                    score=metric.score,
                    raw_value=metric.raw_value,
                    unit=metric.unit,
                )
                for metric in job.result.metric_scores
            ],
            feedback_items=[
                FeedbackItemOut(
                    item_type=item.item_type,
                    title=item.title,
                    description=item.description,
                    metric_code=item.metric_code,
                    evidence=item.evidence,
                    sort_order=item.sort_order,
                )
                for item in job.result.feedback_items
            ],
        )

    return AnalysisJobStatusResponse(
        analysis_job_id=job.id,
        status=job.status,
        current_stage=job.current_stage,
        progress_percent=job.progress_percent,
        error_code=job.error_code,
        error_message=job.error_message,
        result=result_out,
    )
