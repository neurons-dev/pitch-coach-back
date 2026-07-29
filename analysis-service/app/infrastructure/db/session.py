from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine = create_engine(get_settings().database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


@contextmanager
def transaction_scope() -> Iterator[Session]:
    with SessionLocal.begin() as session:
        yield session


@contextmanager
def read_session_scope() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
