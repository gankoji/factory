"""Manager-side backlog dispatcher."""

from __future__ import annotations

import logging
import time

from software_factory.core.backlog.interface import BacklogInterface
from software_factory.core.queue.interface import QueueInterface, QueueItem
from software_factory.services.manager.control_state import ControlState

logger = logging.getLogger(__name__)


class DispatcherService:
    """Continuously enqueue ready backlog tickets for runners."""

    def __init__(
        self,
        backlog: BacklogInterface,
        queue: QueueInterface,
        control_state: ControlState,
        poll_interval_seconds: float = 15.0,
        batch_size: int = 25,
    ):
        self.backlog = backlog
        self.queue = queue
        self.control_state = control_state
        self.poll_interval_seconds = poll_interval_seconds
        self.batch_size = batch_size

    def run_forever(self) -> None:
        """Run dispatch loop forever."""

        logger.info("Dispatcher service started")
        while True:
            enqueued = self.run_once()
            if enqueued == 0:
                time.sleep(self.poll_interval_seconds)

    def run_once(self) -> int:
        """Fetch one batch of ready tickets and enqueue them."""

        if self.control_state.is_paused():
            logger.info("Dispatch paused")
            return 0

        scan_limit = max(self.batch_size * 5, self.batch_size)
        ready = self.backlog.fetch_ready(limit=scan_limit)
        enqueued = 0
        for ticket in ready:
            if self.queue.enqueue(QueueItem(ticket_id=ticket.id)):
                enqueued += 1
                if enqueued >= self.batch_size:
                    break

        if enqueued > 0:
            logger.info("Dispatched %s tickets", enqueued)
        return enqueued
