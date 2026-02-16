"""Backlog behavior tests."""

from __future__ import annotations

import concurrent.futures
import time

from sqlalchemy.orm import Session, sessionmaker

from software_factory.core.backlog.sqlalchemy_backlog import SQLAlchemyBacklog
from software_factory.core.models import TicketStatus
from tests.helpers import make_ticket


def test_create_ticket_is_idempotent(backlog: SQLAlchemyBacklog) -> None:
    first = backlog.create_ticket(make_ticket(ticket_id="ENG-1", idempotency_key="same-key"))
    second = backlog.create_ticket(make_ticket(ticket_id="ENG-2", idempotency_key="same-key"))

    assert first.id == second.id
    assert first.idempotency_key == second.idempotency_key


def test_claim_ticket_allows_only_one_winner(backlog: SQLAlchemyBacklog) -> None:
    created = backlog.create_ticket(make_ticket(ticket_id="ENG-10", idempotency_key="claim-key"))

    def _claim(owner: str) -> bool:
        lease = backlog.claim_ticket(created.id, owner)
        return lease is not None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(_claim, [f"worker-{i}" for i in range(20)]))

    assert sum(results) == 1


def test_claim_ticket_after_expired_lease(backlog: SQLAlchemyBacklog) -> None:
    created = backlog.create_ticket(make_ticket(ticket_id="ENG-11", idempotency_key="exp-key"))

    first = backlog.claim_ticket(created.id, "worker-a")
    assert first is not None

    time.sleep(1.1)
    second = backlog.claim_ticket(created.id, "worker-b")
    assert second is not None
    assert second.token != first.token


def test_terminal_updates_require_valid_lease(backlog: SQLAlchemyBacklog) -> None:
    created = backlog.create_ticket(make_ticket(ticket_id="ENG-12", idempotency_key="term-key"))
    lease = backlog.claim_ticket(created.id, "worker-a")
    assert lease is not None

    assert backlog.complete_ticket(created.id, "invalid") is None

    completed = backlog.complete_ticket(created.id, lease.token)
    assert completed is not None
    assert completed.status == TicketStatus.COMPLETED


def test_failed_ticket_increments_attempts(session_factory: sessionmaker[Session]) -> None:
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=10)
    created = backlog.create_ticket(make_ticket(ticket_id="ENG-13", idempotency_key="fail-key"))
    lease = backlog.claim_ticket(created.id, "worker-a")
    assert lease is not None

    failed = backlog.fail_ticket(created.id, lease.token, reason="test")
    assert failed is not None
    assert failed.status == TicketStatus.FAILED
    assert failed.attempts == 1
