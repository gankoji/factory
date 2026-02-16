"""Queue abstraction used by dispatchers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class QueueItem:
    """Minimal queued item payload."""

    ticket_id: str


class QueueInterface(ABC):
    """Queue contract."""

    @abstractmethod
    def enqueue(self, item: QueueItem) -> None:
        """Push an item onto ready queue."""

    @abstractmethod
    def dequeue(self) -> QueueItem | None:
        """Pop next item from ready queue."""

    @abstractmethod
    def dead_letter(self, item: QueueItem, reason: str) -> None:
        """Move item to dead-letter set."""

    @abstractmethod
    def pending_count(self) -> int:
        """Return ready queue depth."""
