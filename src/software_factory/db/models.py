"""ORM models for persisted control-plane state."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from software_factory.core.models import RunState, TicketStatus
from software_factory.db.base import Base


def utcnow() -> datetime:
    """UTC now helper for defaults."""

    return datetime.now(UTC)


TICKET_STATUS_ENUM = Enum(
    TicketStatus,
    values_callable=lambda values: [item.value for item in values],
    native_enum=False,
    length=32,
)

RUN_STATE_ENUM = Enum(
    RunState,
    values_callable=lambda values: [item.value for item in values],
    native_enum=False,
    length=32,
)


class TicketRow(Base):
    """Persisted backlog ticket record."""

    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    repo: Mapped[str] = mapped_column(String(255), nullable=False)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    acceptance_criteria: Mapped[list] = mapped_column(JSON, default=list)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(TICKET_STATUS_ENUM, default=TicketStatus.READY)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class RunRow(Base):
    """Persisted run record."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    harness: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[RunState] = mapped_column(RUN_STATE_ENUM, nullable=False)
    sandbox_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_token: Mapped[str] = mapped_column(String(64), nullable=False)

    max_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class RunEventRow(Base):
    """Append-only run event ledger."""

    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True, nullable=False)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class LeaseRow(Base):
    """Lease history table for auditability."""

    __tablename__ = "leases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ArtifactRow(Base):
    """Artifact metadata for each run."""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True, nullable=False)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


Index("ix_tickets_ready_status", TicketRow.status)
Index("ix_tickets_lease_expiry", TicketRow.lease_expires_at)
Index("ix_runs_state", RunRow.state)
Index("ix_runs_heartbeat", RunRow.heartbeat_at)
