from __future__ import annotations

import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.interface.exception_handlers import register_exception_handlers
from app.interface.api.jobs import router as analysis_jobs_router
from app.interface.schemas.errors import ErrorResponse

logging.basicConfig(level=get_settings().log_level)

app = FastAPI(title="analysis-service")
register_exception_handlers(app)
app.include_router(analysis_jobs_router)


@app.get(
    "/health",
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def health() -> dict[str, str]:
    return {"status": "ok"}
