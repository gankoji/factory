"""Test helper constructors."""

from __future__ import annotations

from software_factory.core.models import Ticket, TicketPriority


def make_ticket(ticket_id: str = "ENG-1001", idempotency_key: str = "ticket-key-1") -> Ticket:
    """Construct a test ticket."""

    return Ticket(
        id=ticket_id,
        source="sentry",
        type="bug",
        priority=TicketPriority.HIGH,
        repo="example/repo",
        context={"error": "TypeError"},
        acceptance_criteria=["tests pass"],
        idempotency_key=idempotency_key,
    )
