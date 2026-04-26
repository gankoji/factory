"""Shared control-plane pause state."""

from __future__ import annotations

from typing import Protocol, cast

from redis import Redis


class ControlState(Protocol):
    """Control-plane pause-state interface."""

    def is_paused(self) -> bool:
        """Return True when dispatch is paused."""

    def set_paused(self, paused: bool) -> None:
        """Set dispatch pause state."""


class RedisControlState(ControlState):
    """Redis-backed pause-state store shared across manager services."""

    def __init__(self, redis_client: Redis, key: str = "factory:control:paused"):
        self.redis_client = redis_client
        self.key = key

    def is_paused(self) -> bool:
        raw = cast(bytes | str | None, self.redis_client.get(self.key))
        if raw is None:
            return False
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return raw == "1"

    def set_paused(self, paused: bool) -> None:
        self.redis_client.set(self.key, "1" if paused else "0")
