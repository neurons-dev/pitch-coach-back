from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.infrastructure.db.job_repository import SqlAlchemyJobRepository
from app.infrastructure.db.session import DatabaseSessionProvider
from app.interface.api.jobs import router as analysis_jobs_router
from app.interface.exception_handlers import register_exception_handlers
from app.interface.schemas.errors import ErrorResponse

logging.basicConfig(level=get_settings().log_level)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    session_provider = DatabaseSessionProvider(settings=settings, role="api")
    application.state.job_repository = SqlAlchemyJobRepository(
        session_provider=session_provider
    )
    logger = logging.getLogger(__name__)
    logger.info(
        "database connection budget planned=%s available=%s",
        settings.planned_database_connections,
        settings.usable_database_connections,
    )
    session_provider.log_pool_status("api_startup")
    try:
        yield
    finally:
        session_provider.log_pool_status("api_shutdown")
        session_provider.dispose()


app = FastAPI(title="analysis-service", lifespan=lifespan)
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
