from __future__ import annotations

import logging
import signal
import threading

from app.core.config import get_settings

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)

_stop_event = threading.Event()


def _handle_signal(signum: int, _frame: object) -> None:
    logger.info("worker received signal=%s, shutting down", signum)
    _stop_event.set()


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    logger.info("analysis-worker started")
    _stop_event.wait()
    logger.info("analysis-worker stopped")


if __name__ == "__main__":
    main()
