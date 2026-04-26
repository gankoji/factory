"""Queue-driven runner service."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from software_factory.core.adapters.interface import AgentAdapter
from software_factory.core.models import RunState, Ticket, TicketPriority, TicketStatus
from software_factory.core.queue.interface import QueueInterface
from software_factory.db.models import TicketRow
from software_factory.services.execution.runner import ExecutionRunner

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunnerTaskSpec:
    """Resolved execution inputs for a queued ticket."""

    ticket: Ticket
    repo_url: str
    repo: str
    harness: str
    base_branch: str
    head_branch: str | None
    instruction: str | None
    validate_commands: list[str] | None
    existing_pr_number: int | None
    push_branch: bool


class RunnerService:
    """Poll queue and execute ticket runs through execution runner."""

    def __init__(
        self,
        queue: QueueInterface,
        execution_runner: ExecutionRunner,
        session_factory: sessionmaker[Session],
        adapters: dict[str, AgentAdapter],
        owner: str,
        poll_interval_seconds: float = 5.0,
        default_base_branch: str = "main",
        push_branches: bool = False,
    ):
        self.queue = queue
        self.execution_runner = execution_runner
        self.session_factory = session_factory
        self.adapters = adapters
        self.owner = owner
        self.poll_interval_seconds = poll_interval_seconds
        self.default_base_branch = default_base_branch
        self.push_branches = push_branches

    def run_forever(self) -> None:
        """Continuously process queue items."""

        logger.info("Runner service started owner=%s", self.owner)
        while True:
            processed = self.run_once()
            if not processed:
                time.sleep(self.poll_interval_seconds)

    def run_once(self) -> bool:
        """Process one queue item if available."""

        item = self.queue.dequeue()
        if item is None:
            return False

        ticket = self._get_ticket(item.ticket_id)
        if ticket is None:
            self.queue.dead_letter(item, "ticket_not_found")
            logger.warning("Dead-lettered unknown ticket_id=%s", item.ticket_id)
            return True

        task_or_error = self._resolve_task_spec(ticket)
        if isinstance(task_or_error, str):
            self._mark_ticket_failed(ticket.id, task_or_error)
            self.queue.dead_letter(item, task_or_error)
            logger.warning("Dead-lettered ticket_id=%s reason=%s", ticket.id, task_or_error)
            return True

        task = task_or_error
        outcome = self.execution_runner.run_ticket(
            ticket=task.ticket,
            owner=self.owner,
            harness=task.harness,
            repo_url=task.repo_url,
            repo=task.repo,
            base_branch=task.base_branch,
            head_branch=task.head_branch,
            instruction=task.instruction,
            validate_commands=task.validate_commands,
            existing_pr_number=task.existing_pr_number,
            push_branch=task.push_branch,
        )
        if outcome is None:
            status = self._get_ticket_status(item.ticket_id)
            if status == TicketStatus.READY:
                self.queue.enqueue(item)
            return True

        if outcome.state != RunState.SUCCEEDED:
            self.queue.dead_letter(item, f"run_{outcome.state.value}")
            logger.warning("Run failed run_id=%s state=%s", outcome.run_id, outcome.state.value)
        else:
            logger.info(
                "Run succeeded run_id=%s ticket_id=%s pr_url=%s",
                outcome.run_id,
                ticket.id,
                outcome.pr_url,
            )
        return True

    def _resolve_task_spec(self, ticket: Ticket) -> RunnerTaskSpec | str:
        context = ticket.context

        repo_url_raw = context.get("repo_url")
        if not isinstance(repo_url_raw, str) or not repo_url_raw:
            return "missing_repo_url"

        repo_raw = context.get("repo")
        repo = repo_raw if isinstance(repo_raw, str) and repo_raw else ticket.repo

        harness = self._select_harness(ticket, context)
        if harness is None:
            return "no_supported_harness"

        base_branch_raw = context.get("base_branch")
        base_branch = (
            base_branch_raw
            if isinstance(base_branch_raw, str) and base_branch_raw
            else self.default_base_branch
        )

        head_branch_raw = context.get("head_branch")
        head_branch = head_branch_raw if isinstance(head_branch_raw, str) and head_branch_raw else None

        instruction_raw = context.get("instruction")
        instruction = instruction_raw if isinstance(instruction_raw, str) and instruction_raw else None

        validate_commands = self._parse_validate_commands(context.get("validate_commands"))

        existing_pr_raw = context.get("existing_pr_number")
        existing_pr_number = existing_pr_raw if isinstance(existing_pr_raw, int) else None

        push_branch_raw = context.get("push_branch")
        push_branch = push_branch_raw if isinstance(push_branch_raw, bool) else self.push_branches

        return RunnerTaskSpec(
            ticket=ticket,
            repo_url=repo_url_raw,
            repo=repo,
            harness=harness,
            base_branch=base_branch,
            head_branch=head_branch,
            instruction=instruction,
            validate_commands=validate_commands,
            existing_pr_number=existing_pr_number,
            push_branch=push_branch,
        )

    def _select_harness(self, ticket: Ticket, context: dict[str, object]) -> str | None:
        preferred = context.get("harness")
        if isinstance(preferred, str):
            adapter = self.adapters.get(preferred)
            if adapter and adapter.supports(ticket.type):
                return preferred
            return None

        for name, adapter in self.adapters.items():
            if adapter.supports(ticket.type):
                return name
        return None

    def _parse_validate_commands(self, value: object) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            return [value]
        if isinstance(value, list) and all(isinstance(item, str) and item for item in value):
            return list(value)
        return None

    def _get_ticket(self, ticket_id: str) -> Ticket | None:
        with self.session_factory() as session:
            row = session.execute(select(TicketRow).where(TicketRow.id == ticket_id)).scalar_one_or_none()
            if row is None:
                return None
            return self._ticket_from_row(row)

    def _get_ticket_status(self, ticket_id: str) -> TicketStatus | None:
        with self.session_factory() as session:
            row = session.execute(select(TicketRow).where(TicketRow.id == ticket_id)).scalar_one_or_none()
            if row is None:
                return None
            return row.status

    def _mark_ticket_failed(self, ticket_id: str, reason: str) -> None:
        with self.session_factory() as session:
            row = session.execute(select(TicketRow).where(TicketRow.id == ticket_id)).scalar_one_or_none()
            if row is None:
                return
            row.status = TicketStatus.FAILED
            row.attempts += 1
            row.last_failure_reason = reason
            row.updated_at = datetime.now(UTC)
            session.commit()

    def _ticket_from_row(self, row: TicketRow) -> Ticket:
        return Ticket(
            id=row.id,
            source=row.source,
            type=row.type,
            priority=TicketPriority(row.priority),
            repo=row.repo,
            context=row.context,
            acceptance_criteria=list(row.acceptance_criteria),
            idempotency_key=row.idempotency_key,
            status=row.status,
            attempts=row.attempts,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
