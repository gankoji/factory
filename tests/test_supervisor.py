"""Run supervisor tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from software_factory.core.backlog.sqlalchemy_backlog import SQLAlchemyBacklog
from software_factory.core.models import RunBudget, RunState, TicketStatus
from software_factory.core.supervisor.run_supervisor import RunSupervisor
from software_factory.db.models import RunRow, TicketRow
from tests.helpers import make_ticket


def test_dispatch_creates_run_and_claims_ticket(session_factory: sessionmaker[Session]) -> None:
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=30)
    supervisor = RunSupervisor(backlog=backlog, session_factory=session_factory, heartbeat_timeout_seconds=1)

    created = backlog.create_ticket(make_ticket(ticket_id="ENG-20", idempotency_key="run-key"))
    run = supervisor.dispatch(
        ticket_id=created.id,
        owner="runner-1",
        harness="codex",
        budget=RunBudget(max_minutes=10, max_tokens=1000),
    )

    assert run is not None
    assert run.state == RunState.CLAIMED

    with session_factory() as session:
        ticket = session.execute(select(TicketRow).where(TicketRow.id == created.id)).scalar_one()
        assert ticket.status == TicketStatus.CLAIMED


def test_invalid_transition_is_rejected(session_factory: sessionmaker[Session]) -> None:
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=30)
    supervisor = RunSupervisor(backlog=backlog, session_factory=session_factory, heartbeat_timeout_seconds=1)

    created = backlog.create_ticket(make_ticket(ticket_id="ENG-21", idempotency_key="run-key-2"))
    run = supervisor.dispatch(
        ticket_id=created.id,
        owner="runner-1",
        harness="codex",
        budget=RunBudget(max_minutes=10, max_tokens=1000),
    )
    assert run is not None

    result = supervisor.monitor_run(run.run_id, RunState.SUCCEEDED)
    assert result is None


def test_succeeded_run_completes_ticket(session_factory: sessionmaker[Session]) -> None:
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=30)
    supervisor = RunSupervisor(backlog=backlog, session_factory=session_factory, heartbeat_timeout_seconds=1)

    created = backlog.create_ticket(make_ticket(ticket_id="ENG-22", idempotency_key="run-key-3"))
    run = supervisor.dispatch(
        ticket_id=created.id,
        owner="runner-1",
        harness="codex",
        budget=RunBudget(max_minutes=10, max_tokens=1000),
    )
    assert run is not None

    running = supervisor.monitor_run(run.run_id, RunState.RUNNING)
    assert running is not None

    success = supervisor.monitor_run(run.run_id, RunState.SUCCEEDED)
    assert success is not None
    assert success.state == RunState.SUCCEEDED

    with session_factory() as session:
        ticket = session.execute(select(TicketRow).where(TicketRow.id == created.id)).scalar_one()
        assert ticket.status == TicketStatus.COMPLETED


def test_recover_stale_runs_marks_timeout(session_factory: sessionmaker[Session]) -> None:
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=30)
    supervisor = RunSupervisor(backlog=backlog, session_factory=session_factory, heartbeat_timeout_seconds=1)

    created = backlog.create_ticket(make_ticket(ticket_id="ENG-23", idempotency_key="run-key-4"))
    run = supervisor.dispatch(
        ticket_id=created.id,
        owner="runner-1",
        harness="codex",
        budget=RunBudget(max_minutes=10, max_tokens=1000),
    )
    assert run is not None
    _ = supervisor.monitor_run(run.run_id, RunState.RUNNING)

    with session_factory() as session:
        row = session.execute(select(RunRow).where(RunRow.id == run.run_id)).scalar_one()
        row.heartbeat_at = datetime.now(UTC) - timedelta(seconds=30)
        session.commit()

    recovered = supervisor.recover_stale_runs()
    assert run.run_id in recovered
