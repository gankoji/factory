"""Runner service queue-loop tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from software_factory.core.adapters.interface import AgentAdapter
from software_factory.core.backlog.sqlalchemy_backlog import SQLAlchemyBacklog
from software_factory.core.git.github_pr import GitHubPRClient
from software_factory.core.models import TicketStatus
from software_factory.core.queue.interface import QueueInterface, QueueItem
from software_factory.core.sandbox import SandboxManager
from software_factory.core.supervisor.run_supervisor import RunSupervisor
from software_factory.db.models import RunRow, TicketRow
from software_factory.services.execution.runner import ExecutionRunner
from software_factory.services.runner.service import RunnerService
from tests.helpers import create_git_remote, make_ticket


class FakeQueue(QueueInterface):
    """In-memory queue for deterministic tests."""

    def __init__(self, initial: list[QueueItem] | None = None):
        self.items = list(initial or [])
        self.dead_items: list[tuple[QueueItem, str]] = []
        self.enqueued_ids = {item.ticket_id for item in self.items}

    def enqueue(self, item: QueueItem) -> bool:
        if item.ticket_id in self.enqueued_ids:
            return False
        self.items.append(item)
        self.enqueued_ids.add(item.ticket_id)
        return True

    def dequeue(self) -> QueueItem | None:
        if not self.items:
            return None
        item = self.items.pop(0)
        self.enqueued_ids.discard(item.ticket_id)
        return item

    def dead_letter(self, item: QueueItem, reason: str) -> None:
        self.enqueued_ids.discard(item.ticket_id)
        self.dead_items.append((item, reason))

    def pending_count(self) -> int:
        return len(self.items)


class FakeWriteAdapter(AgentAdapter):
    """Adapter that writes a file inside sandbox repo."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}

    def supports(self, ticket_type: str, repo_language: str | None = None) -> bool:
        return ticket_type in {"bug", "chore", "test-gap"}

    def launch_task(self, task_payload: dict[str, Any]) -> str:
        sandbox = task_payload["sandbox"]
        run_id = task_payload["run_id"]
        repo_path = task_payload["repo_path"]
        result = sandbox.run_command("echo 'runner service' > generated.txt", run_id=run_id, workdir=repo_path)
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


def _build_service(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
    queue: QueueInterface,
    adapters: dict[str, AgentAdapter],
) -> RunnerService:
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=60)
    supervisor = RunSupervisor(backlog=backlog, session_factory=session_factory, heartbeat_timeout_seconds=30)
    sandbox = SandboxManager(workspace_root=tmp_path / "workspaces", use_local_mode=True)

    execution_runner = ExecutionRunner(
        backlog=backlog,
        supervisor=supervisor,
        sandbox_manager=sandbox,
        adapters=adapters,
        pr_client=GitHubPRClient(token=None, dry_run=True),
        session_factory=session_factory,
        artifacts_root=tmp_path / "artifacts",
    )

    return RunnerService(
        queue=queue,
        execution_runner=execution_runner,
        session_factory=session_factory,
        adapters=adapters,
        owner="runner-test",
        poll_interval_seconds=0.01,
    )


def test_run_once_processes_queue_item_success(session_factory: sessionmaker[Session], tmp_path: Path) -> None:
    remote = create_git_remote(tmp_path / "remote")
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=60)

    ticket = backlog.create_ticket(
        make_ticket(
            ticket_id="ENG-4001",
            idempotency_key="runner-success",
            context={
                "repo_url": remote,
                "instruction": "create generated file",
                "validate_commands": ["test -f generated.txt"],
                "harness": "fake",
            },
        )
    )

    queue = FakeQueue(initial=[QueueItem(ticket_id=ticket.id)])
    service = _build_service(session_factory, tmp_path, queue=queue, adapters={"fake": FakeWriteAdapter()})

    processed = service.run_once()
    assert processed is True
    assert queue.dead_items == []

    with session_factory() as session:
        ticket_row = session.execute(select(TicketRow).where(TicketRow.id == ticket.id)).scalar_one()
        run_row = session.execute(select(RunRow).where(RunRow.ticket_id == ticket.id)).scalar_one()

        assert ticket_row.status == TicketStatus.COMPLETED
        assert run_row.state.value == "succeeded"


def test_run_once_dead_letters_invalid_ticket_context(
    session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=60)
    ticket = backlog.create_ticket(
        make_ticket(
            ticket_id="ENG-4002",
            idempotency_key="runner-invalid",
            context={"harness": "fake"},
        )
    )

    queue = FakeQueue(initial=[QueueItem(ticket_id=ticket.id)])
    service = _build_service(session_factory, tmp_path, queue=queue, adapters={"fake": FakeWriteAdapter()})

    processed = service.run_once()
    assert processed is True
    assert len(queue.dead_items) == 1
    assert queue.dead_items[0][1] == "missing_repo_url"

    with session_factory() as session:
        ticket_row = session.execute(select(TicketRow).where(TicketRow.id == ticket.id)).scalar_one()
        assert ticket_row.status == TicketStatus.FAILED
        assert ticket_row.last_failure_reason == "missing_repo_url"


def test_run_once_dead_letters_when_no_supported_harness(
    session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    remote = create_git_remote(tmp_path / "remote-nosupport")
    backlog = SQLAlchemyBacklog(session_factory=session_factory, lease_ttl_seconds=60)
    ticket = backlog.create_ticket(
        make_ticket(
            ticket_id="ENG-4003",
            idempotency_key="runner-no-harness",
            context={"repo_url": remote, "harness": "missing"},
        )
    )

    queue = FakeQueue(initial=[QueueItem(ticket_id=ticket.id)])
    service = _build_service(session_factory, tmp_path, queue=queue, adapters={"fake": FakeWriteAdapter()})

    processed = service.run_once()
    assert processed is True
    assert len(queue.dead_items) == 1
    assert queue.dead_items[0][1] == "no_supported_harness"
