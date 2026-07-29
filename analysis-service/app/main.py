from __future__ import annotations

import logging

from fastapi import FastAPI

from app.core.config import get_settings

logging.basicConfig(level=get_settings().log_level)

app = FastAPI(title="analysis-service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
