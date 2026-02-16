"""Test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from software_factory.core.backlog.sqlalchemy_backlog import SQLAlchemyBacklog
from software_factory.db.base import Base


@pytest.fixture()
def session_factory(tmp_path: Path) -> sessionmaker[Session]:
    """Provide an isolated sqlite session factory for each test."""

    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture()
def backlog(session_factory: sessionmaker[Session]) -> SQLAlchemyBacklog:
    """Provide SQLAlchemy backlog implementation."""

    return SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=1)
