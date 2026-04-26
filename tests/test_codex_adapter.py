"""Codex adapter tests."""

from __future__ import annotations

from software_factory.core.adapters.codex import CodexAdapter
from software_factory.core.sandbox import CommandResult


class FakeSandbox:
    """Minimal sandbox stub for adapter tests."""

    def __init__(self, exit_code: int = 0):
        self.exit_code = exit_code

    def run_command(self, cmd: str, run_id: str, workdir: str | None = None) -> CommandResult:
        if self.exit_code == 0:
            return CommandResult(
                command=cmd,
                stdout="ok",
                stderr="",
                exit_code=0,
                duration_seconds=0.1,
            )
        return CommandResult(
            command=cmd,
            stdout="",
            stderr="boom",
            exit_code=1,
            duration_seconds=0.1,
        )


def test_codex_adapter_success_flow() -> None:
    adapter = CodexAdapter(binary="echo")

    session_id = adapter.launch_task(
        {
            "sandbox": FakeSandbox(exit_code=0),
            "run_id": "run-1",
            "instruction": "make change",
            "repo_path": "/tmp/repo",
        }
    )

    assert adapter.supports("bug") is True
    events = adapter.stream_events(session_id)
    assert [event["event"] for event in events] == ["task_started", "task_completed"]

    artifacts = adapter.collect_artifacts(session_id)
    assert artifacts["exit_code"] == 0


def test_codex_adapter_failure_flow() -> None:
    adapter = CodexAdapter(binary="echo")

    session_id = adapter.launch_task(
        {
            "sandbox": FakeSandbox(exit_code=1),
            "run_id": "run-2",
            "instruction": "break",
            "repo_path": "/tmp/repo",
        }
    )

    events = adapter.stream_events(session_id)
    assert events[-1]["event"] == "task_failed"
    artifacts = adapter.collect_artifacts(session_id)
    assert artifacts["exit_code"] == 1
