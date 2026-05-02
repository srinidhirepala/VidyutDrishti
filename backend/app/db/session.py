"""Engine + session factory.

The engine is lazily constructed so importing the module does not
require a reachable database (important for tests and migration
generation). ``get_session`` is the FastAPI dependency used from the
API layer.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


@lru_cache(maxsize=1)
def _make_engine() -> Engine:
    # Imported here so that `from backend.app.db import Base` does not
    # immediately try to read the settings / environment.
    from app.config import get_settings

    s = get_settings()
    return create_engine(s.database_url, pool_pre_ping=True, future=True)


class _LazyEngine:
    """A tiny proxy so `from backend.app.db import engine` works even
    before the settings are populated. Any real attribute access forces
    engine creation.
    """

    def __getattr__(self, item: str):  # pragma: no cover - passthrough
        return getattr(_make_engine(), item)


engine = _LazyEngine()


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=_make_engine(), autoflush=False, autocommit=False, future=True)


def SessionLocal() -> Session:  # noqa: N802 - keep the classic alias name
    return _session_factory()()


def get_session() -> Iterator[Session]:
    """FastAPI dependency - yields a session and closes it on exit."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
