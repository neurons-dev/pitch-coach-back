from __future__ import annotations

import logging
import signal
import threading

from app.application.workers.dispatcher import Dispatcher
from app.application.workers.watchdog import Watchdog
from app.core.config import get_settings
from app.infrastructure.db.job_repository import SqlAlchemyJobRepository

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)

_stop_event = threading.Event()


def _handle_signal(signum: int, _frame: object) -> None:
    logger.info("worker received signal=%s, shutting down", signum)
    _stop_event.set()


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    job_repository = SqlAlchemyJobRepository()
    dispatcher = Dispatcher(job_repository=job_repository)
    watchdog = Watchdog(job_repository=job_repository)

    dispatcher.start()
    watchdog.start()
    logger.info("analysis-worker started")

    _stop_event.wait()

    dispatcher.stop()
    watchdog.stop()
    logger.info("analysis-worker stopped")


if __name__ == "__main__":
    main()
