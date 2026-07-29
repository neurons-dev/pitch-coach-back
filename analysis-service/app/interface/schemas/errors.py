from __future__ import annotations

from pydantic import Field

from app.interface.schemas.common import CamelModel


class ErrorDetail(CamelModel):
    field: str | None = None
    message: str
    type: str


class ErrorResponse(CamelModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
