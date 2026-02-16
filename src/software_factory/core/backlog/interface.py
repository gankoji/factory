"""Backlog interface abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

from software_factory.core.models import Lease, Ticket


class BacklogInterface(ABC):
    """Storage-agnostic backlog contract."""

    @abstractmethod
    def fetch_ready(self, limit: int = 50) -> list[Ticket]:
        """Return ready tickets ordered by priority and age."""

    @abstractmethod
    def create_ticket(self, ticket: Ticket) -> Ticket:
        """Create a ticket in idempotent manner based on idempotency_key."""

    @abstractmethod
    def claim_ticket(self, ticket_id: str, owner: str) -> Lease | None:
        """Attempt to claim a ticket; return lease if successful."""

    @abstractmethod
    def heartbeat(self, ticket_id: str, lease_token: str) -> Lease | None:
        """Renew an existing lease."""

    @abstractmethod
    def complete_ticket(self, ticket_id: str, lease_token: str) -> Ticket | None:
        """Mark ticket completed if lease is valid."""

    @abstractmethod
    def fail_ticket(self, ticket_id: str, lease_token: str, reason: str | None = None) -> Ticket | None:
        """Mark ticket failed if lease is valid."""
