"""Test helper constructors."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from software_factory.core.models import Ticket, TicketPriority


def make_ticket(
    ticket_id: str = "ENG-1001",
    idempotency_key: str = "ticket-key-1",
    *,
    repo: str = "example/repo",
    ticket_type: str = "bug",
    context: dict[str, Any] | None = None,
    acceptance_criteria: list[str] | None = None,
) -> Ticket:
    """Construct a test ticket."""

    return Ticket(
        id=ticket_id,
        source="sentry",
        type=ticket_type,
        priority=TicketPriority.HIGH,
        repo=repo,
        context=context or {"error": "TypeError"},
        acceptance_criteria=acceptance_criteria or ["tests pass"],
        idempotency_key=idempotency_key,
    )


def create_git_remote(tmp_path: Path) -> str:
    """Create a bare git remote with a seeded `main` branch and return its path."""

    seed_repo = tmp_path / "seed"
    bare_repo = tmp_path / "remote.git"
    seed_repo.mkdir(parents=True, exist_ok=True)

    _run("git init", cwd=seed_repo)
    _run("git config user.email 'bot@example.com'", cwd=seed_repo)
    _run("git config user.name 'Factory Bot'", cwd=seed_repo)
    (seed_repo / "README.md").write_text("# Seed\\n")
    _run("git add README.md", cwd=seed_repo)
    _run("git commit -m 'seed'", cwd=seed_repo)
    _run("git branch -M main", cwd=seed_repo)

    _run(f"git init --bare {bare_repo}", cwd=tmp_path)
    _run(f"git -C {bare_repo} symbolic-ref HEAD refs/heads/main", cwd=tmp_path)
    _run(f"git remote add origin {bare_repo}", cwd=seed_repo)
    _run("git push -u origin main", cwd=seed_repo)
    return str(bare_repo.resolve())


def _run(cmd: str, cwd: Path) -> None:
    subprocess.run([ "bash", "-lc", cmd], cwd=cwd, check=True, capture_output=True, text=True)
