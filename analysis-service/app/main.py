from __future__ import annotations

import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.interface.api.jobs import router as analysis_jobs_router

logging.basicConfig(level=get_settings().log_level)

app = FastAPI(title="analysis-service")
app.include_router(analysis_jobs_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
