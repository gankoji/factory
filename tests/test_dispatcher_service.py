"""Manager dispatcher service tests."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from software_factory.core.backlog.sqlalchemy_backlog import SQLAlchemyBacklog
from software_factory.core.queue.interface import QueueInterface, QueueItem
from software_factory.services.manager.dispatcher import DispatcherService
from tests.helpers import make_ticket


class FakeControlState:
    """Simple pause-state stub."""

    def __init__(self, paused: bool = False):
        self.paused = paused

    def is_paused(self) -> bool:
        return self.paused

    def set_paused(self, paused: bool) -> None:
        self.paused = paused


class FakeQueue(QueueInterface):
    """In-memory unique queue implementation."""

    def __init__(self) -> None:
        self.items: list[QueueItem] = []
        self.ids: set[str] = set()
        self.dead_items: list[tuple[QueueItem, str]] = []

    def enqueue(self, item: QueueItem) -> bool:
        if item.ticket_id in self.ids:
            return False
        self.ids.add(item.ticket_id)
        self.items.append(item)
        return True

    def dequeue(self) -> QueueItem | None:
        if not self.items:
            return None
        item = self.items.pop(0)
        self.ids.discard(item.ticket_id)
        return item

    def dead_letter(self, item: QueueItem, reason: str) -> None:
        self.ids.discard(item.ticket_id)
        self.dead_items.append((item, reason))

    def pending_count(self) -> int:
        return len(self.items)


def test_dispatcher_enqueues_ready_tickets_with_batch_limit(
    session_factory: sessionmaker[Session],
) -> None:
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=60)

    t1 = backlog.create_ticket(make_ticket(ticket_id="ENG-D1", idempotency_key="d-1"))
    t2 = backlog.create_ticket(make_ticket(ticket_id="ENG-D2", idempotency_key="d-2"))
    t3 = backlog.create_ticket(make_ticket(ticket_id="ENG-D3", idempotency_key="d-3"))

    queue = FakeQueue()
    dispatcher = DispatcherService(
        backlog=backlog,
        queue=queue,
        control_state=FakeControlState(paused=False),
        batch_size=2,
        poll_interval_seconds=0.01,
    )

    first = dispatcher.run_once()
    assert first == 2
    assert queue.pending_count() == 2

    second = dispatcher.run_once()
    assert second == 1
    assert queue.pending_count() == 3
    assert {item.ticket_id for item in queue.items} == {t1.id, t2.id, t3.id}


def test_dispatcher_respects_pause_state(session_factory: sessionmaker[Session]) -> None:
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=60)
    _ = backlog.create_ticket(make_ticket(ticket_id="ENG-D4", idempotency_key="d-4"))

    queue = FakeQueue()
    control = FakeControlState(paused=True)
    dispatcher = DispatcherService(
        backlog=backlog,
        queue=queue,
        control_state=control,
        batch_size=5,
        poll_interval_seconds=0.01,
    )

    assert dispatcher.run_once() == 0
    assert queue.pending_count() == 0

    control.set_paused(False)
    assert dispatcher.run_once() == 1
    assert queue.pending_count() == 1
