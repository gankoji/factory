"""Redis-backed queue implementation."""

from __future__ import annotations

import json
from typing import cast

from redis import Redis

from software_factory.core.queue.interface import QueueInterface, QueueItem


class RedisQueue(QueueInterface):
    """Simple Redis list-backed queue with dead-letter list."""

    def __init__(
        self,
        redis_client: Redis,
        name: str = "factory:ready",
        dlq_name: str = "factory:dlq",
        queued_set_name: str = "factory:queued",
    ):
        self.redis_client = redis_client
        self.name = name
        self.dlq_name = dlq_name
        self.queued_set_name = queued_set_name

    def enqueue(self, item: QueueItem) -> bool:
        inserted = cast(int, self.redis_client.sadd(self.queued_set_name, item.ticket_id))
        if inserted != 1:
            return False
        self.redis_client.rpush(self.name, json.dumps({"ticket_id": item.ticket_id}))
        return True

    def dequeue(self) -> QueueItem | None:
        payload = cast(str | bytes | None, self.redis_client.lpop(self.name))
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        data = json.loads(payload)
        ticket_id = str(data["ticket_id"])
        self.redis_client.srem(self.queued_set_name, ticket_id)
        return QueueItem(ticket_id=ticket_id)

    def dead_letter(self, item: QueueItem, reason: str) -> None:
        self.redis_client.srem(self.queued_set_name, item.ticket_id)
        self.redis_client.rpush(
            self.dlq_name,
            json.dumps({"ticket_id": item.ticket_id, "reason": reason}),
        )

    def pending_count(self) -> int:
        return cast(int, self.redis_client.llen(self.name))
