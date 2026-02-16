"""Backlog domain errors."""

from __future__ import annotations


class BacklogError(Exception):
    """Base backlog error."""


class TicketConflictError(BacklogError):
    """Raised when claim/create operation conflicts with current ticket state."""
