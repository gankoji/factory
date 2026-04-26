"""Execution runner tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from software_factory.core.adapters.interface import AgentAdapter
from software_factory.core.backlog.sqlalchemy_backlog import SQLAlchemyBacklog
from software_factory.core.git.github_pr import GitHubPRClient
from software_factory.core.models import RunState, TicketStatus
from software_factory.core.sandbox import SandboxManager
from software_factory.core.supervisor.run_supervisor import RunSupervisor
from software_factory.db.models import ArtifactRow, RunRow, TicketRow
from software_factory.services.execution.runner import ExecutionRunner
from tests.helpers import create_git_remote, make_ticket


class FakeWriteAdapter(AgentAdapter):
    """Adapter that writes a file inside the sandbox repo."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}

    def supports(self, ticket_type: str, repo_language: str | None = None) -> bool:
        return True

    def launch_task(self, task_payload: dict[str, Any]) -> str:
        sandbox = task_payload["sandbox"]
        run_id = task_payload["run_id"]
        repo_path = task_payload["repo_path"]
        result = sandbox.run_command(
            "echo 'generated' > generated.txt",
            run_id=run_id,
            workdir=repo_path,
        )
        session_id = str(uuid4())
        self.sessions[session_id] = {
            "events": [
                {"event": "task_started"},
                {"event": "task_completed" if result.exit_code == 0 else "task_failed"},
            ],
            "artifacts": {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
            },
        }
        return session_id

    def stream_events(self, session_id: str) -> list[dict[str, Any]]:
        return list(self.sessions[session_id]["events"])

    def send_control(self, session_id: str, control: str) -> None:
        self.sessions[session_id]["events"].append({"event": "control", "action": control})

    def collect_artifacts(self, session_id: str) -> dict[str, Any]:
        return dict(self.sessions[session_id]["artifacts"])

    def terminate(self, session_id: str) -> None:
        self.sessions[session_id]["events"].append({"event": "terminated"})


def test_execution_runner_success(
    session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=60)
    supervisor = RunSupervisor(backlog=backlog, session_factory=session_factory, heartbeat_timeout_seconds=30)
    sandbox = SandboxManager(workspace_root=tmp_path / "workspaces", use_local_mode=True)

    ticket = backlog.create_ticket(make_ticket(ticket_id="ENG-3001", idempotency_key="run-success"))
    remote = create_git_remote(tmp_path / "remote_source")

    runner = ExecutionRunner(
        backlog=backlog,
        supervisor=supervisor,
        sandbox_manager=sandbox,
        adapters={"fake": FakeWriteAdapter()},
        pr_client=GitHubPRClient(token=None, dry_run=True),
        session_factory=session_factory,
        artifacts_root=tmp_path / "artifacts",
    )

    outcome = runner.run_ticket(
        ticket=ticket,
        owner="runner-1",
        harness="fake",
        repo_url=remote,
        repo="org/repo",
        instruction="create generated.txt",
        validate_commands=["test -f generated.txt"],
    )

    assert outcome is not None
    assert outcome.state == RunState.SUCCEEDED
    assert outcome.pr_url is not None
    assert "dry-run" in outcome.pr_url

    with session_factory() as session:
        ticket_row = session.execute(select(TicketRow).where(TicketRow.id == ticket.id)).scalar_one()
        run_row = session.execute(select(RunRow).where(RunRow.ticket_id == ticket.id)).scalar_one()
        artifacts = session.execute(select(ArtifactRow).where(ArtifactRow.ticket_id == ticket.id)).scalars()

        assert ticket_row.status == TicketStatus.COMPLETED
        assert run_row.state == RunState.SUCCEEDED
        assert len(list(artifacts)) >= 4


def test_execution_runner_validation_failure(
    session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=60)
    supervisor = RunSupervisor(backlog=backlog, session_factory=session_factory, heartbeat_timeout_seconds=30)
    sandbox = SandboxManager(workspace_root=tmp_path / "workspaces", use_local_mode=True)

    ticket = backlog.create_ticket(make_ticket(ticket_id="ENG-3002", idempotency_key="run-failure"))
    remote = create_git_remote(tmp_path / "remote_source_fail")

    runner = ExecutionRunner(
        backlog=backlog,
        supervisor=supervisor,
        sandbox_manager=sandbox,
        adapters={"fake": FakeWriteAdapter()},
        pr_client=GitHubPRClient(token=None, dry_run=True),
        session_factory=session_factory,
        artifacts_root=tmp_path / "artifacts",
    )

    outcome = runner.run_ticket(
        ticket=ticket,
        owner="runner-1",
        harness="fake",
        repo_url=remote,
        repo="org/repo",
        instruction="create generated.txt",
        validate_commands=["test -f not-there.txt"],
    )

    assert outcome is not None
    assert outcome.state == RunState.FAILED
    assert outcome.pr_url is None

    with session_factory() as session:
        ticket_row = session.execute(select(TicketRow).where(TicketRow.id == ticket.id)).scalar_one()
        run_row = session.execute(select(RunRow).where(RunRow.ticket_id == ticket.id)).scalar_one()

        assert ticket_row.status == TicketStatus.FAILED
        assert run_row.state == RunState.FAILED
