"""Run supervisor core state machine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from software_factory.config import get_settings
from software_factory.core.backlog.interface import BacklogInterface
from software_factory.core.models import Run, RunBudget, RunState, TicketStatus
from software_factory.db.models import RunEventRow, RunRow, TicketRow

TERMINAL_STATES: set[RunState] = {
    RunState.SUCCEEDED,
    RunState.FAILED,
    RunState.TIMED_OUT,
    RunState.CANCELED,
}

ALLOWED_TRANSITIONS: dict[RunState, set[RunState]] = {
    RunState.CLAIMED: {RunState.RUNNING, RunState.CANCELED, RunState.TIMED_OUT, RunState.FAILED},
    RunState.RUNNING: {
        RunState.BLOCKED,
        RunState.SUCCEEDED,
        RunState.FAILED,
        RunState.TIMED_OUT,
        RunState.CANCELED,
        RunState.AWAITING_APPROVAL,
    },
    RunState.BLOCKED: {RunState.RUNNING, RunState.CANCELED, RunState.TIMED_OUT, RunState.FAILED},
    RunState.AWAITING_APPROVAL: {RunState.RUNNING, RunState.CANCELED, RunState.TIMED_OUT},
    RunState.SUCCEEDED: set(),
    RunState.FAILED: set(),
    RunState.TIMED_OUT: set(),
    RunState.CANCELED: set(),
}


class RunSupervisor:
    """Dispatch and lifecycle management for ticket runs."""

    def __init__(
        self,
        backlog: BacklogInterface,
        session_factory: sessionmaker[Session],
        heartbeat_timeout_seconds: int | None = None,
    ):
        self.backlog = backlog
        self.session_factory = session_factory
        self.heartbeat_timeout_seconds = (
            heartbeat_timeout_seconds or get_settings().run_heartbeat_timeout_seconds
        )

    def dispatch(self, ticket_id: str, owner: str, harness: str, budget: RunBudget) -> Run | None:
        """Claim a ticket and create a new run."""

        lease = self.backlog.claim_ticket(ticket_id=ticket_id, owner=owner)
        if lease is None:
            return None

        now = datetime.now(UTC)
        run = Run(
            run_id=str(uuid4()),
            ticket_id=ticket_id,
            harness=harness,
            state=RunState.CLAIMED,
            lease_token=lease.token,
            budget=budget,
            started_at=now,
            heartbeat_at=now,
        )

        with self.session_factory() as session:
            session.add(
                RunRow(
                    id=run.run_id,
                    ticket_id=run.ticket_id,
                    harness=run.harness,
                    state=run.state,
                    lease_token=run.lease_token,
                    max_minutes=run.budget.max_minutes,
                    max_tokens=run.budget.max_tokens,
                    token_count=0,
                    started_at=run.started_at,
                    heartbeat_at=run.heartbeat_at,
                )
            )
            session.add(
                RunEventRow(
                    run_id=run.run_id,
                    ticket_id=run.ticket_id,
                    event_type="run_claimed",
                    payload={"owner": owner, "harness": harness},
                )
            )
            session.commit()

        return run

    def monitor_run(
        self,
        run_id: str,
        new_state: RunState,
        token_delta: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> Run | None:
        """Transition run state and record a run event."""

        now = datetime.now(UTC)
        payload = payload or {}

        with self.session_factory() as session:
            run_row = session.execute(select(RunRow).where(RunRow.id == run_id)).scalar_one_or_none()
            if run_row is None:
                return None

            current_state = run_row.state
            if new_state not in ALLOWED_TRANSITIONS[current_state]:
                return None

            run_row.state = new_state
            run_row.token_count += token_delta
            run_row.heartbeat_at = now
            if new_state in TERMINAL_STATES:
                run_row.ended_at = now

            session.add(
                RunEventRow(
                    run_id=run_row.id,
                    ticket_id=run_row.ticket_id,
                    event_type="state_transition",
                    payload={
                        "from": current_state.value,
                        "to": new_state.value,
                        **payload,
                    },
                )
            )

            if new_state == RunState.SUCCEEDED:
                self.backlog.complete_ticket(run_row.ticket_id, run_row.lease_token)
                self._update_ticket_status(session, run_row.ticket_id, TicketStatus.COMPLETED)
            elif new_state in {RunState.FAILED, RunState.TIMED_OUT, RunState.CANCELED}:
                self.backlog.fail_ticket(run_row.ticket_id, run_row.lease_token, reason=new_state.value)
                self._update_ticket_status(session, run_row.ticket_id, TicketStatus.FAILED)

            session.commit()
            return self._to_model(run_row)

    def enforce_limits(self, run_id: str, token_count: int | None = None) -> Run | None:
        """Apply budget constraints to a run and timeout if limits are exceeded."""

        now = datetime.now(UTC)
        with self.session_factory() as session:
            run_row = session.execute(select(RunRow).where(RunRow.id == run_id)).scalar_one_or_none()
            if run_row is None:
                return None

            runtime_exceeded = now > run_row.started_at + timedelta(minutes=run_row.max_minutes)
            token_exceeded = token_count is not None and token_count > run_row.max_tokens

            if runtime_exceeded or token_exceeded:
                reason = "max_minutes" if runtime_exceeded else "max_tokens"
                run_row.error_message = f"Budget exceeded: {reason}"
                session.commit()
                return self.monitor_run(
                    run_id,
                    RunState.TIMED_OUT,
                    payload={"reason": reason, "token_count": token_count},
                )

            if token_count is not None:
                run_row.token_count = token_count
                run_row.heartbeat_at = now
                session.add(
                    RunEventRow(
                        run_id=run_row.id,
                        ticket_id=run_row.ticket_id,
                        event_type="budget_check",
                        payload={"token_count": token_count},
                    )
                )
                session.commit()

            return self._to_model(run_row)

    def recover_stale_runs(self) -> list[str]:
        """Mark runs timed_out if heartbeat is stale beyond configured timeout."""

        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=self.heartbeat_timeout_seconds)
        recovered: list[str] = []

        with self.session_factory() as session:
            stale_runs = session.execute(
                select(RunRow).where(
                    RunRow.state.in_([RunState.CLAIMED, RunState.RUNNING, RunState.BLOCKED]),
                    RunRow.heartbeat_at < cutoff,
                )
            ).scalars()
            stale_ids = [row.id for row in stale_runs]

        for run_id in stale_ids:
            result = self.monitor_run(run_id, RunState.TIMED_OUT, payload={"reason": "stale_heartbeat"})
            if result is not None:
                recovered.append(run_id)

        return recovered

    def _to_model(self, row: RunRow) -> Run:
        return Run(
            run_id=row.id,
            ticket_id=row.ticket_id,
            harness=row.harness,
            state=row.state,
            sandbox_id=row.sandbox_id,
            lease_token=row.lease_token,
            budget=RunBudget(max_minutes=row.max_minutes, max_tokens=row.max_tokens),
            token_count=row.token_count,
            started_at=row.started_at,
            heartbeat_at=row.heartbeat_at,
            ended_at=row.ended_at,
            error_message=row.error_message,
        )

    def _update_ticket_status(self, session: Session, ticket_id: str, status: TicketStatus) -> None:
        ticket_row = session.execute(select(TicketRow).where(TicketRow.id == ticket_id)).scalar_one_or_none()
        if ticket_row is not None:
            ticket_row.status = status
