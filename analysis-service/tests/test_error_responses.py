from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.domain.errors import IdempotencyKeyConflictError
from app.interface.dependencies import get_job_repository
from app.main import app


class _FakeJobRepository:
    def __init__(
        self,
        *,
        job: object | None = None,
        create_error: Exception | None = None,
        get_error: Exception | None = None,
    ) -> None:
        self._job = job
        self._create_error = create_error
        self._get_error = get_error

    def create_job(self, **_kwargs):
        if self._create_error is not None:
            raise self._create_error
        raise AssertionError("create_job was not expected")

    def get_job(self, _job_id: uuid.UUID):
        if self._get_error is not None:
            raise self._get_error
        return self._job


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _use_repository(repository: _FakeJobRepository) -> None:
    app.dependency_overrides[get_job_repository] = lambda: repository


def _auth_headers() -> dict[str, str]:
    return {"X-Internal-Token": get_settings().internal_token}


def _create_request() -> dict[str, object]:
    return {
        "sessionId": str(uuid.uuid4()),
        "userId": 1,
        "audioObjectKey": "private/test/audio.m4a",
    }


def test_invalid_internal_token_uses_common_error_response(client: TestClient):
    # given
    _use_repository(_FakeJobRepository())

    # when
    response = client.get(
        f"/internal/v1/analysis-jobs/{uuid.uuid4()}",
        headers={"X-Internal-Token": "invalid"},
    )

    # then
    assert response.status_code == 401
    assert response.json() == {
        "code": "INVALID_INTERNAL_TOKEN",
        "message": "Invalid internal token.",
        "details": [],
    }


def test_missing_job_uses_common_error_response(client: TestClient):
    # given
    _use_repository(_FakeJobRepository(job=None))

    # when
    response = client.get(
        f"/internal/v1/analysis-jobs/{uuid.uuid4()}",
        headers=_auth_headers(),
    )

    # then
    assert response.status_code == 404
    assert response.json() == {
        "code": "ANALYSIS_JOB_NOT_FOUND",
        "message": "Analysis job not found.",
        "details": [],
    }


def test_idempotency_conflict_uses_common_error_response(client: TestClient):
    # given
    _use_repository(
        _FakeJobRepository(
            create_error=IdempotencyKeyConflictError("different request"),
        )
    )

    # when
    response = client.post(
        "/internal/v1/analysis-jobs",
        json=_create_request(),
        headers={
            **_auth_headers(),
            "Idempotency-Key": "same-key",
        },
    )

    # then
    assert response.status_code == 409
    assert response.json() == {
        "code": "IDEMPOTENCY_KEY_CONFLICT",
        "message": "The idempotency key was already used with a different request.",
        "details": [],
    }


def test_request_validation_uses_common_error_response(client: TestClient):
    # given
    _use_repository(_FakeJobRepository())

    # when
    response = client.get(
        "/internal/v1/analysis-jobs/not-a-uuid",
        headers=_auth_headers(),
    )

    # then
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Request validation failed."
    assert body["details"][0]["field"] == "jobId"
    assert body["details"][0]["type"] == "uuid_parsing"
    assert "input" not in body["details"][0]
    assert "msg" not in body["details"][0]


def test_unexpected_exception_hides_internal_details(client: TestClient):
    # given
    _use_repository(
        _FakeJobRepository(
            get_error=RuntimeError("database password and internal SQL"),
        )
    )

    # when
    response = client.get(
        f"/internal/v1/analysis-jobs/{uuid.uuid4()}",
        headers=_auth_headers(),
    )

    # then
    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL_SERVER_ERROR",
        "message": "An unexpected error occurred.",
        "details": [],
    }
    assert "database password" not in response.text


def test_openapi_uses_common_error_response_schema(client: TestClient):
    # given
    error_responses = {
        ("/internal/v1/analysis-jobs", "post", "401"),
        ("/internal/v1/analysis-jobs", "post", "409"),
        ("/internal/v1/analysis-jobs", "post", "422"),
        ("/internal/v1/analysis-jobs", "post", "500"),
        ("/internal/v1/analysis-jobs/{job_id}", "get", "401"),
        ("/internal/v1/analysis-jobs/{job_id}", "get", "404"),
        ("/internal/v1/analysis-jobs/{job_id}", "get", "422"),
        ("/internal/v1/analysis-jobs/{job_id}", "get", "500"),
    }

    # when
    schema = client.get("/openapi.json").json()

    # then
    properties = schema["components"]["schemas"]["ErrorResponse"]["properties"]
    assert set(properties) == {"code", "message", "details"}
    assert "msg" not in properties
    for path, method, status_code in error_responses:
        response_schema = schema["paths"][path][method]["responses"][status_code]["content"][
            "application/json"
        ]["schema"]
        assert response_schema["$ref"] == "#/components/schemas/ErrorResponse"
