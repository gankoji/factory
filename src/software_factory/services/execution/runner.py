"""Execution runner orchestrating claim -> sandbox -> harness -> validate -> PR."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from software_factory.config import get_settings
from software_factory.core.adapters.interface import AgentAdapter
from software_factory.core.backlog.interface import BacklogInterface
from software_factory.core.git.github_pr import GitHubPRClient, build_pr_body
from software_factory.core.models import Artifact, ArtifactType, RunBudget, RunState, Ticket
from software_factory.core.sandbox.manager import SandboxManager
from software_factory.core.supervisor.run_supervisor import RunSupervisor
from software_factory.db.models import ArtifactRow, RunRow


@dataclass(frozen=True)
class RunOutcome:
    """Summary of an execution runner attempt."""

    run_id: str
    state: RunState
    pr_url: str | None
    evidence: dict[str, str]


class ExecutionRunner:
    """Run tickets through harness and governance-ready PR submission flow."""

    def __init__(
        self,
        backlog: BacklogInterface,
        supervisor: RunSupervisor,
        sandbox_manager: SandboxManager,
        adapters: dict[str, AgentAdapter],
        pr_client: GitHubPRClient,
        session_factory: sessionmaker[Session],
        artifacts_root: Path | str = Path("artifacts"),
    ):
        self.backlog = backlog
        self.supervisor = supervisor
        self.sandbox_manager = sandbox_manager
        self.adapters = adapters
        self.pr_client = pr_client
        self.session_factory = session_factory
        self.artifacts_root = Path(artifacts_root)
        self.artifacts_root.mkdir(parents=True, exist_ok=True)

    def run_ticket(
        self,
        *,
        ticket: Ticket,
        owner: str,
        harness: str,
        repo_url: str,
        repo: str,
        base_branch: str = "main",
        head_branch: str | None = None,
        instruction: str | None = None,
        validate_commands: list[str] | None = None,
        existing_pr_number: int | None = None,
        push_branch: bool = False,
        budget: RunBudget | None = None,
    ) -> RunOutcome | None:
        """Execute a single ticket end-to-end and return run outcome."""

        selected_adapter = self.adapters.get(harness)
        if selected_adapter is None:
            raise ValueError(f"Unknown adapter: {harness}")

        settings = get_settings()
        budget = budget or RunBudget(
            max_minutes=settings.max_run_minutes,
            max_tokens=settings.max_run_tokens,
        )

        run = self.supervisor.dispatch(
            ticket_id=ticket.id,
            owner=owner,
            harness=harness,
            budget=budget,
        )
        if run is None:
            return None

        active_head = head_branch or f"robot/{ticket.id.lower()}-{run.run_id[:8]}"
        evidence: dict[str, str] = {}

        self.supervisor.monitor_run(run.run_id, RunState.RUNNING)

        try:
            session = self.sandbox_manager.provision(repo_url=repo_url, branch=base_branch, run_id=run.run_id)
            self._set_sandbox_id(run.run_id, session.container_id or f"local:{session.workspace_path}")

            checkout = self.sandbox_manager.run_command(
                f"git checkout -B {active_head}",
                run_id=run.run_id,
                workdir=session.repo_path,
            )
            if checkout.exit_code != 0:
                raise RuntimeError(f"Failed to create work branch {active_head}: {checkout.stderr}")

            adapter_session_id = self.sandbox_manager.run_harness(
                selected_adapter,
                {
                    "instruction": instruction
                    or f"Implement ticket {ticket.id}. Meet acceptance criteria and keep tests passing.",
                },
                run_id=run.run_id,
            )
            events = selected_adapter.stream_events(adapter_session_id)
            adapter_artifacts = selected_adapter.collect_artifacts(adapter_session_id)

            harness_exit = int(adapter_artifacts.get("exit_code", 1))
            harness_stdout = str(adapter_artifacts.get("stdout", ""))
            harness_stderr = str(adapter_artifacts.get("stderr", ""))

            evidence["harness_stdout"] = self._write_artifact(
                run_id=run.run_id,
                ticket_id=ticket.id,
                artifact_name="harness_stdout.log",
                artifact_type=ArtifactType.LOG,
                contents=harness_stdout,
                metadata={"events": events},
            )
            evidence["harness_stderr"] = self._write_artifact(
                run_id=run.run_id,
                ticket_id=ticket.id,
                artifact_name="harness_stderr.log",
                artifact_type=ArtifactType.LOG,
                contents=harness_stderr,
                metadata={"events": events},
            )

            if harness_exit != 0:
                raise RuntimeError(f"Harness execution failed with exit_code={harness_exit}")

            validate_commands = validate_commands or ["git status --short"]
            validation_results: list[dict[str, Any]] = []
            for cmd in validate_commands:
                result = self.sandbox_manager.run_command(cmd, run_id=run.run_id, workdir=session.repo_path)
                validation_results.append(
                    {
                        "command": cmd,
                        "exit_code": result.exit_code,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    }
                )
                if result.exit_code != 0:
                    raise RuntimeError(f"Validation command failed: {cmd}\n{result.stderr}")

            evidence["validation"] = self._write_artifact(
                run_id=run.run_id,
                ticket_id=ticket.id,
                artifact_name="validation.json",
                artifact_type=ArtifactType.TEST_REPORT,
                contents=json.dumps(validation_results, indent=2),
                metadata={"count": len(validation_results)},
            )

            diff_result = self.sandbox_manager.run_command(
                "git diff --binary",
                run_id=run.run_id,
                workdir=session.repo_path,
            )
            evidence["patch"] = self._write_artifact(
                run_id=run.run_id,
                ticket_id=ticket.id,
                artifact_name="changes.patch",
                artifact_type=ArtifactType.PATCH,
                contents=diff_result.stdout,
                metadata={"exit_code": diff_result.exit_code},
            )

            if push_branch:
                push_result = self.sandbox_manager.run_command(
                    f"git push -u origin {active_head}",
                    run_id=run.run_id,
                    workdir=session.repo_path,
                )
                if push_result.exit_code != 0:
                    raise RuntimeError(f"Branch push failed: {push_result.stderr}")

            pr_title = f"[{ticket.id}] Automated changes"
            pr_body = build_pr_body(ticket.id, run.run_id, ticket.acceptance_criteria, evidence)
            pr_ref = self.pr_client.create_or_update_pull_request(
                repo=repo,
                head=active_head,
                base=base_branch,
                title=pr_title,
                body=pr_body,
                existing_number=existing_pr_number,
            )
            evidence["pr"] = self._write_artifact(
                run_id=run.run_id,
                ticket_id=ticket.id,
                artifact_name="pull_request.json",
                artifact_type=ArtifactType.OTHER,
                contents=json.dumps({"number": pr_ref.number, "url": pr_ref.url}, indent=2),
                metadata={"url": pr_ref.url, "number": pr_ref.number},
            )

            self.supervisor.monitor_run(run.run_id, RunState.SUCCEEDED, payload={"pr_url": pr_ref.url})
            return RunOutcome(
                run_id=run.run_id,
                state=RunState.SUCCEEDED,
                pr_url=pr_ref.url,
                evidence=evidence,
            )
        except Exception as exc:
            self.supervisor.monitor_run(
                run.run_id,
                RunState.FAILED,
                payload={"error": str(exc)},
            )
            return RunOutcome(
                run_id=run.run_id,
                state=RunState.FAILED,
                pr_url=None,
                evidence=evidence,
            )
        finally:
            self.sandbox_manager.teardown(run.run_id)

    def _write_artifact(
        self,
        *,
        run_id: str,
        ticket_id: str,
        artifact_name: str,
        artifact_type: ArtifactType,
        contents: str,
        metadata: dict[str, Any],
    ) -> str:
        run_dir = self.artifacts_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = run_dir / artifact_name
        artifact_path.write_text(contents)

        artifact = Artifact(
            run_id=run_id,
            ticket_id=ticket_id,
            type=artifact_type,
            uri=str(artifact_path.resolve()),
            metadata=metadata,
        )
        with self.session_factory() as session:
            session.add(
                ArtifactRow(
                    id=artifact.id,
                    run_id=artifact.run_id,
                    ticket_id=artifact.ticket_id,
                    artifact_type=artifact.type.value,
                    uri=artifact.uri,
                    artifact_metadata=artifact.metadata,
                    created_at=artifact.created_at,
                )
            )
            session.commit()

        return artifact.uri

    def _set_sandbox_id(self, run_id: str, sandbox_id: str) -> None:
        with self.session_factory() as session:
            run_row = session.execute(select(RunRow).where(RunRow.id == run_id)).scalar_one_or_none()
            if run_row is not None:
                run_row.sandbox_id = sandbox_id
                session.commit()
