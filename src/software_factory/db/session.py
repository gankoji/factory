"""Database engine and session utilities."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from software_factory.config import get_settings


def create_engine_from_settings() -> Engine:
    """Build a SQLAlchemy engine from configured settings."""

    settings = get_settings()
    return create_engine(settings.database_url, future=True)


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Create a configured session factory."""

    if engine is None:
        engine = create_engine_from_settings()
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
