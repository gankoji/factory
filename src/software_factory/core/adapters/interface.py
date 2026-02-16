"""Agent harness adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AgentAdapter(ABC):
    """Contract for external harness integrations."""

    @abstractmethod
    def supports(self, ticket_type: str, repo_language: str | None = None) -> bool:
        """Return whether adapter supports this workload."""

    @abstractmethod
    def launch_task(self, task_payload: dict[str, Any]) -> str:
        """Launch a harness task and return session id."""

    @abstractmethod
    def stream_events(self, session_id: str) -> list[dict[str, Any]]:
        """Read incremental events for a harness session."""

    @abstractmethod
    def send_control(self, session_id: str, control: str) -> None:
        """Send a control instruction to the harness."""

    @abstractmethod
    def collect_artifacts(self, session_id: str) -> dict[str, Any]:
        """Collect task outputs and artifacts."""

    @abstractmethod
    def terminate(self, session_id: str) -> None:
        """Terminate a harness session."""
