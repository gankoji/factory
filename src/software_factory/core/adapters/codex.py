"""Codex CLI adapter implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from software_factory.core.adapters.interface import AgentAdapter


@dataclass
class _SessionState:
    events: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    consumed: bool = False


class CodexAdapter(AgentAdapter):
    """Adapter that executes Codex CLI inside a sandbox."""

    def __init__(self, binary: str = "codex", command_mode: str = "exec"):
        self.binary = binary
        self.command_mode = command_mode
        self._sessions: dict[str, _SessionState] = {}

    def supports(self, ticket_type: str, repo_language: str | None = None) -> bool:
        supported_types = {"bug", "test-gap", "chore", "feature", "maintenance"}
        return ticket_type in supported_types

    def launch_task(self, task_payload: dict[str, Any]) -> str:
        sandbox = task_payload["sandbox"]
        run_id = task_payload["run_id"]
        instruction = task_payload.get("instruction", "Implement the requested ticket changes.")
        workdir = task_payload.get("repo_path")

        session_id = str(uuid4())
        state = _SessionState()
        state.events.append({"event": "task_started", "run_id": run_id})

        command = self._build_command(instruction)
        result = sandbox.run_command(command, run_id=run_id, workdir=workdir)

        if result.exit_code == 0:
            state.events.append({"event": "task_completed", "run_id": run_id})
        else:
            state.events.append(
                {
                    "event": "task_failed",
                    "run_id": run_id,
                    "exit_code": result.exit_code,
                    "stderr": result.stderr,
                }
            )

        state.artifacts = {
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "duration_seconds": result.duration_seconds,
        }
        self._sessions[session_id] = state
        return session_id

    def stream_events(self, session_id: str) -> list[dict[str, Any]]:
        state = self._sessions[session_id]
        if state.consumed:
            return []
        state.consumed = True
        return list(state.events)

    def send_control(self, session_id: str, control: str) -> None:
        state = self._sessions[session_id]
        state.events.append({"event": "control", "action": control})

    def collect_artifacts(self, session_id: str) -> dict[str, Any]:
        return dict(self._sessions[session_id].artifacts)

    def terminate(self, session_id: str) -> None:
        state = self._sessions.get(session_id)
        if state is not None:
            state.events.append({"event": "terminated"})

    def _build_command(self, instruction: str) -> str:
        escaped = instruction.replace('"', '\\"')
        if self.command_mode == "exec":
            return f'{self.binary} exec --json "{escaped}"'
        return f'{self.binary} "{escaped}"'
