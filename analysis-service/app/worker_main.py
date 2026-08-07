from __future__ import annotations

import logging
import signal
import threading

from app.application.analysis.analysis_use_case import AnalysisUseCase
from app.application.workers.dispatcher import Dispatcher
from app.application.workers.watchdog import Watchdog
from app.core.config import get_settings
from app.infrastructure.audio.normalizer import FfmpegAudioNormalizer
from app.infrastructure.audio.storage import S3AudioStorage
from app.infrastructure.audio.transcriber import FasterWhisperTranscriber
from app.infrastructure.db.job_repository import SqlAlchemyJobRepository
from app.infrastructure.db.session import DatabaseSessionProvider
from app.infrastructure.feedback.factory import create_feedback_generator
from app.infrastructure.pronunciation.factory import create_pronunciation_assessor

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)

_stop_event = threading.Event()


def _handle_signal(signum: int, _frame: object) -> None:
    logger.info("worker received signal=%s, shutting down", signum)
    _stop_event.set()


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    settings = get_settings()
    session_provider = DatabaseSessionProvider(settings=settings, role="worker")
    logger.info(
        "database connection budget planned=%s available=%s",
        settings.planned_database_connections,
        settings.usable_database_connections,
    )
    session_provider.log_pool_status("worker_startup")
    job_repository = SqlAlchemyJobRepository(session_provider=session_provider)
    analysis_use_case = AnalysisUseCase(
        audio_storage=S3AudioStorage(settings=settings),
        audio_normalizer=FfmpegAudioNormalizer(),
        speech_transcriber=FasterWhisperTranscriber(settings=settings),
        pronunciation_assessor=create_pronunciation_assessor(settings),
        feedback_generator=create_feedback_generator(settings),
        pipeline_version=settings.pipeline_version,
    )
    dispatcher = Dispatcher(
        job_repository=job_repository,
        lease_duration_seconds=settings.lease_duration_seconds,
        worker_poll_interval_seconds=settings.worker_poll_interval_seconds,
        lease_heartbeat_interval_seconds=settings.lease_heartbeat_interval_seconds,
        analysis_runner=analysis_use_case.run,
        analysis_boundary_observer=session_provider.log_pool_status,
    )
    watchdog = Watchdog(
        job_repository=job_repository,
        watchdog_check_interval_seconds=settings.watchdog_check_interval_seconds,
        batch_size=settings.watchdog_batch_size,
        max_batches_per_cycle=settings.watchdog_max_batches_per_cycle,
        max_run_seconds=settings.watchdog_max_run_seconds,
        connection_acquire_timeout_seconds=settings.db_pool_timeout_seconds,
    )

    try:
        dispatcher.start()
        watchdog.start()
        logger.info("analysis-worker started")
        _stop_event.wait()
    finally:
        watchdog.stop()
        dispatcher.stop()
        session_provider.log_pool_status("worker_shutdown")
        session_provider.dispose()
        logger.info("analysis-worker stopped")


if __name__ == "__main__":
    main()
