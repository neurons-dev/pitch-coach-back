from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings

DatabaseRole = Literal["api", "worker"]
logger = logging.getLogger(__name__)


class DatabaseSessionProvider:
    def __init__(self, *, settings: Settings, role: DatabaseRole) -> None:
        self.role = role
        self.pool_size = settings.db_pool_size(role)
        self.max_overflow = settings.db_max_overflow(role)
        self.engine = create_engine(
            settings.database_url,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=settings.db_pool_timeout_seconds,
            pool_recycle=settings.db_pool_recycle_seconds,
            pool_pre_ping=True,
            future=True,
            connect_args={
                "application_name": f"analysis-service-{role}",
                "options": " ".join(
                    (
                        f"-c statement_timeout={settings.db_statement_timeout_ms}",
                        f"-c lock_timeout={settings.db_lock_timeout_ms}",
                        "-c idle_in_transaction_session_timeout="
                        f"{settings.db_idle_in_transaction_session_timeout_ms}",
                    )
                ),
            },
        )
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        logger.info(
            "database pool configured role=%s pool_size=%s max_overflow=%s "
            "pool_timeout_seconds=%s pool_recycle_seconds=%s",
            role,
            self.pool_size,
            self.max_overflow,
            settings.db_pool_timeout_seconds,
            settings.db_pool_recycle_seconds,
        )

    @contextmanager
    def transaction_scope(self) -> Iterator[Session]:
        with self.session_factory.begin() as session:
            yield session

    @contextmanager
    def read_session_scope(self) -> Iterator[Session]:
        with self.session_factory() as session:
            yield session

    def pool_snapshot(self) -> dict[str, int]:
        pool = self.engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": max(0, pool.overflow()),
        }

    def log_pool_status(self, event: str) -> None:
        snapshot = self.pool_snapshot()
        logger.info(
            "database pool status role=%s event=%s size=%s checked_in=%s "
            "checked_out=%s overflow=%s",
            self.role,
            event,
            snapshot["size"],
            snapshot["checked_in"],
            snapshot["checked_out"],
            snapshot["overflow"],
        )

    def dispose(self) -> None:
        self.engine.dispose()
        logger.info("database pool disposed role=%s", self.role)
