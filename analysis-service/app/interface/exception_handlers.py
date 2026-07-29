from __future__ import annotations

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic.alias_generators import to_camel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.interface.exceptions import ApiException
from app.interface.schemas.errors import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

_HTTP_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
}


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiException, _api_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unexpected_exception_handler)


def _response(*, status_code: int, error: ErrorResponse) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error.model_dump(mode="json", by_alias=True),
    )


async def _api_exception_handler(_request: Request, exc: ApiException) -> JSONResponse:
    return _response(
        status_code=exc.status_code,
        error=ErrorResponse(code=exc.code, message=exc.message, details=exc.details),
    )


async def _validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        ErrorDetail(
            field=_format_location(error.get("loc", ())),
            message=str(error.get("msg", "Invalid value.")),
            type=str(error.get("type", "validation_error")),
        )
        for error in exc.errors()
    ]
    return _response(
        status_code=422,
        error=ErrorResponse(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details=details,
        ),
    )


async def _http_exception_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    status_code = exc.status_code
    code = _HTTP_ERROR_CODES.get(status_code, f"HTTP_{status_code}")
    message = (
        exc.detail
        if isinstance(exc.detail, str)
        else _http_status_message(status_code)
    )
    return _response(
        status_code=status_code,
        error=ErrorResponse(code=code, message=message),
    )


async def _unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled request error method=%s path=%s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return _response(
        status_code=500,
        error=ErrorResponse(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred.",
        ),
    )


def _format_location(location: object) -> str | None:
    if not isinstance(location, (list, tuple)):
        return None
    parts = [
        to_camel(str(part))
        for part in location
        if part not in {"body", "path", "query", "header"}
    ]
    return ".".join(parts) or None


def _http_status_message(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTP request failed."
