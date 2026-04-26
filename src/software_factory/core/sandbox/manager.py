"""Sandbox manager for isolated execution runs."""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from software_factory.core.adapters.interface import AgentAdapter


@dataclass(frozen=True)
class CommandResult:
    """Result of a command executed inside a sandbox."""

    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float


@dataclass(frozen=True)
class SandboxSession:
    """Provisioned sandbox metadata."""

    run_id: str
    workspace_path: Path
    repo_path: Path
    container_id: str | None


class SandboxManager:
    """Provision and manage per-run sandbox sessions.

    The default runtime is local mode for deterministic tests and development.
    Docker runtime is supported when `use_local_mode=False`.
    """

    def __init__(
        self,
        image: str = "software-factory-runner:latest",
        workspace_root: Path | str = Path(".sandbox") / "workspaces",
        use_local_mode: bool = True,
        docker_client: Any | None = None,
    ):
        self.image = image
        self.workspace_root = Path(workspace_root)
        self.use_local_mode = use_local_mode
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self._docker_client = docker_client
        self._sessions: dict[str, SandboxSession] = {}

    def provision(self, repo_url: str, branch: str, run_id: str) -> SandboxSession:
        """Create sandbox, clone target repo, and checkout branch."""

        if run_id in self._sessions:
            return self._sessions[run_id]

        workspace = self.workspace_root / run_id
        repo_path = workspace / "repo"
        workspace.mkdir(parents=True, exist_ok=True)

        if self.use_local_mode:
            self._run_local(
                f"git clone {shlex.quote(repo_url)} {shlex.quote(str(repo_path))}",
                cwd=workspace,
            )
            checkout = self._run_local(
                f"git checkout {shlex.quote(branch)}",
                cwd=repo_path,
            )
            if checkout.exit_code != 0:
                fallback = self._run_local(
                    f"git checkout -b {shlex.quote(branch)}",
                    cwd=repo_path,
                )
                if fallback.exit_code != 0:
                    raise RuntimeError(
                        f"Failed to checkout branch {branch}: {checkout.stderr or fallback.stderr}"
                    )
            session = SandboxSession(
                run_id=run_id,
                workspace_path=workspace,
                repo_path=repo_path,
                container_id=None,
            )
            self._sessions[run_id] = session
            return session

        container = self._start_docker_container(workspace)
        clone_result = self._run_docker(
            container=container,
            cmd=f"git clone {shlex.quote(repo_url)} /workspace/repo",
            workdir="/workspace",
        )
        if clone_result.exit_code != 0:
            self._safe_remove_container(container)
            raise RuntimeError(f"Failed to clone repo: {clone_result.stderr}")

        checkout = self._run_docker(
            container=container,
            cmd=f"git checkout {shlex.quote(branch)}",
            workdir="/workspace/repo",
        )
        if checkout.exit_code != 0:
            fallback = self._run_docker(
                container=container,
                cmd=f"git checkout -b {shlex.quote(branch)}",
                workdir="/workspace/repo",
            )
            if fallback.exit_code != 0:
                self._safe_remove_container(container)
                raise RuntimeError(
                    f"Failed to checkout branch {branch}: {checkout.stderr or fallback.stderr}"
                )

        session = SandboxSession(
            run_id=run_id,
            workspace_path=workspace,
            repo_path=repo_path,
            container_id=container.id,
        )
        self._sessions[run_id] = session
        return session

    def run_command(self, cmd: str, run_id: str, workdir: str | Path | None = None) -> CommandResult:
        """Run command in provisioned sandbox and return structured output."""

        session = self._sessions.get(run_id)
        if session is None:
            raise KeyError(f"Unknown run_id: {run_id}")

        if self.use_local_mode:
            cwd = Path(workdir) if workdir is not None else session.repo_path
            return self._run_local(cmd, cwd=cwd)

        container = self._get_container(session.container_id)
        if container is None:
            raise RuntimeError(f"Missing container for run_id={run_id}")
        docker_workdir = workdir if isinstance(workdir, str) else str(workdir or "/workspace/repo")
        return self._run_docker(container=container, cmd=cmd, workdir=docker_workdir)

    def run_harness(self, adapter: AgentAdapter, task_payload: dict[str, Any], run_id: str) -> str:
        """Launch harness task with sandbox context injected."""

        session = self._sessions.get(run_id)
        if session is None:
            raise KeyError(f"Unknown run_id: {run_id}")

        payload = {
            **task_payload,
            "sandbox": self,
            "run_id": run_id,
            "repo_path": str(session.repo_path),
            "workspace_path": str(session.workspace_path),
        }
        return adapter.launch_task(payload)

    def teardown(self, run_id: str) -> None:
        """Destroy sandbox container and release session resources."""

        session = self._sessions.pop(run_id, None)
        if session is None:
            return

        if not self.use_local_mode and session.container_id is not None:
            container = self._get_container(session.container_id)
            if container is not None:
                self._safe_remove_container(container)

    def _run_local(self, cmd: str, cwd: Path) -> CommandResult:
        start = monotonic()
        proc = subprocess.run(
            ["bash", "-lc", cmd],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        duration = monotonic() - start
        return CommandResult(
            command=cmd,
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            duration_seconds=duration,
        )

    def _get_docker_client(self) -> Any:
        if self._docker_client is not None:
            return self._docker_client
        try:
            import docker  # noqa: PLC0415  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("Docker SDK is required for docker sandbox runtime") from exc

        self._docker_client = docker.from_env()
        return self._docker_client

    def _start_docker_container(self, workspace_path: Path) -> Any:
        client = self._get_docker_client()
        return client.containers.run(
            image=self.image,
            command=["sleep", "infinity"],
            detach=True,
            tty=True,
            working_dir="/workspace",
            volumes={str(workspace_path): {"bind": "/workspace", "mode": "rw"}},
        )

    def _get_container(self, container_id: str | None) -> Any | None:
        if container_id is None:
            return None
        client = self._get_docker_client()
        try:
            return client.containers.get(container_id)
        except Exception:
            return None

    def _run_docker(self, container: Any, cmd: str, workdir: str) -> CommandResult:
        start = monotonic()
        exec_result = container.exec_run(cmd=["bash", "-lc", cmd], workdir=workdir)
        duration = monotonic() - start

        output = exec_result.output
        if isinstance(output, bytes):
            stdout = output.decode("utf-8", errors="replace")
        elif isinstance(output, tuple):
            stdout = "\n".join(
                part.decode("utf-8", errors="replace") if isinstance(part, bytes) else str(part)
                for part in output
            )
        else:
            stdout = str(output)

        return CommandResult(
            command=cmd,
            stdout=stdout,
            stderr="",
            exit_code=int(exec_result.exit_code),
            duration_seconds=duration,
        )

    def _safe_remove_container(self, container: Any) -> None:
        try:
            container.remove(force=True)
        except Exception:
            pass
