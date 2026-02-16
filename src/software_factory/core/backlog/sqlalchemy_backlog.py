"""SQLAlchemy-backed backlog implementation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from software_factory.config import get_settings
from software_factory.core.backlog.interface import BacklogInterface
from software_factory.core.models import Lease, Ticket, TicketPriority, TicketStatus
from software_factory.db.models import LeaseRow, TicketRow

_PRIORITY_ORDER = {
    TicketPriority.CRITICAL.value: 0,
    TicketPriority.HIGH.value: 1,
    TicketPriority.MEDIUM.value: 2,
    TicketPriority.LOW.value: 3,
}


class SQLAlchemyBacklog(BacklogInterface):
    """Backlog adapter using SQLAlchemy session factory."""

    def __init__(self, session_factory: sessionmaker[Session], lease_ttl_seconds: int | None = None):
        self.session_factory = session_factory
        self.lease_ttl_seconds = lease_ttl_seconds or get_settings().default_lease_ttl_seconds

    def fetch_ready(self, limit: int = 50) -> list[Ticket]:
        """Fetch ready tickets sorted by priority and creation timestamp."""

        with self.session_factory() as session:
            rows = session.execute(
                select(TicketRow).where(TicketRow.status == TicketStatus.READY)
            ).scalars()
            ordered = sorted(
                rows,
                key=lambda row: (
                    _PRIORITY_ORDER.get(row.priority, len(_PRIORITY_ORDER)),
                    row.created_at,
                ),
            )
            return [self._to_ticket(row) for row in ordered[:limit]]

    def create_ticket(self, ticket: Ticket) -> Ticket:
        """Idempotently create a new ticket."""

        with self.session_factory() as session:
            existing = session.execute(
                select(TicketRow).where(TicketRow.idempotency_key == ticket.idempotency_key)
            ).scalar_one_or_none()
            if existing:
                return self._to_ticket(existing)

            row = TicketRow(
                id=ticket.id,
                source=ticket.source,
                type=ticket.type,
                priority=ticket.priority.value,
                repo=ticket.repo,
                context=ticket.context,
                acceptance_criteria=ticket.acceptance_criteria,
                idempotency_key=ticket.idempotency_key,
                status=TicketStatus.READY,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                retry = session.execute(
                    select(TicketRow).where(TicketRow.idempotency_key == ticket.idempotency_key)
                ).scalar_one()
                return self._to_ticket(retry)
            session.refresh(row)
            return self._to_ticket(row)

    def claim_ticket(self, ticket_id: str, owner: str) -> Lease | None:
        """Claim a ticket if it is available or has an expired lease."""

        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.lease_ttl_seconds)
        lease_token = str(uuid4())

        with self.session_factory() as session:
            stmt = (
                update(TicketRow)
                .where(
                    and_(
                        TicketRow.id == ticket_id,
                        or_(
                            TicketRow.status == TicketStatus.READY,
                            and_(
                                TicketRow.status == TicketStatus.CLAIMED,
                                TicketRow.lease_expires_at.is_not(None),
                                TicketRow.lease_expires_at < now,
                            ),
                        ),
                    )
                )
                .values(
                    status=TicketStatus.CLAIMED,
                    lease_owner=owner,
                    lease_token=lease_token,
                    lease_expires_at=expires_at,
                    updated_at=now,
                )
            )
            result = cast(CursorResult[tuple[object]], session.execute(stmt))
            if result.rowcount != 1:
                session.rollback()
                return None

            session.add(
                LeaseRow(
                    ticket_id=ticket_id,
                    owner=owner,
                    token=lease_token,
                    expires_at=expires_at,
                )
            )
            session.commit()
            return Lease(ticket_id=ticket_id, owner=owner, token=lease_token, expires_at=expires_at)

    def heartbeat(self, ticket_id: str, lease_token: str) -> Lease | None:
        """Extend a valid lease TTL."""

        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.lease_ttl_seconds)
        with self.session_factory() as session:
            stmt = (
                update(TicketRow)
                .where(
                    and_(
                        TicketRow.id == ticket_id,
                        TicketRow.status == TicketStatus.CLAIMED,
                        TicketRow.lease_token == lease_token,
                        TicketRow.lease_expires_at.is_not(None),
                        TicketRow.lease_expires_at >= now,
                    )
                )
                .values(lease_expires_at=expires_at, updated_at=now)
            )
            result = cast(CursorResult[tuple[object]], session.execute(stmt))
            if result.rowcount != 1:
                session.rollback()
                return None

            lease_row = session.execute(
                select(LeaseRow)
                .where(LeaseRow.token == lease_token)
                .order_by(LeaseRow.id.desc())
            ).scalar_one_or_none()
            if lease_row is not None:
                lease_row.expires_at = expires_at
            session.commit()

            row = session.execute(select(TicketRow).where(TicketRow.id == ticket_id)).scalar_one()
            return Lease(
                ticket_id=row.id,
                owner=row.lease_owner or "",
                token=lease_token,
                expires_at=expires_at,
            )

    def complete_ticket(self, ticket_id: str, lease_token: str) -> Ticket | None:
        """Complete a ticket when caller holds lease token."""

        return self._terminal_update(ticket_id, lease_token, TicketStatus.COMPLETED)

    def fail_ticket(self, ticket_id: str, lease_token: str, reason: str | None = None) -> Ticket | None:
        """Fail a ticket when caller holds lease token."""

        return self._terminal_update(ticket_id, lease_token, TicketStatus.FAILED, reason)

    def _terminal_update(
        self,
        ticket_id: str,
        lease_token: str,
        status: TicketStatus,
        reason: str | None = None,
    ) -> Ticket | None:
        now = datetime.now(UTC)
        with self.session_factory() as session:
            row = session.execute(
                select(TicketRow).where(
                    and_(
                        TicketRow.id == ticket_id,
                        TicketRow.lease_token == lease_token,
                        TicketRow.status == TicketStatus.CLAIMED,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return None

            row.status = status
            row.lease_owner = None
            row.lease_token = None
            row.lease_expires_at = None
            row.updated_at = now
            if status == TicketStatus.FAILED:
                row.attempts += 1
                row.last_failure_reason = reason

            lease = session.execute(
                select(LeaseRow)
                .where(LeaseRow.token == lease_token)
                .order_by(LeaseRow.id.desc())
            ).scalar_one_or_none()
            if lease is not None:
                lease.released_at = now

            session.commit()
            session.refresh(row)
            return self._to_ticket(row)

    def _to_ticket(self, row: TicketRow) -> Ticket:
        return Ticket(
            id=row.id,
            source=row.source,
            type=row.type,
            priority=TicketPriority(row.priority),
            repo=row.repo,
            context=row.context,
            acceptance_criteria=list(row.acceptance_criteria),
            idempotency_key=row.idempotency_key,
            status=row.status,
            attempts=row.attempts,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
