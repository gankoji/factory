"""Sandbox manager tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from software_factory.core.sandbox import SandboxManager
from tests.helpers import create_git_remote


def test_provision_and_run_command_in_local_mode(tmp_path: Path) -> None:
    remote = create_git_remote(tmp_path)
    manager = SandboxManager(workspace_root=tmp_path / "workspaces", use_local_mode=True)

    session = manager.provision(repo_url=remote, branch="main", run_id="run-1")
    assert session.repo_path.exists()

    branch = manager.run_command(
        "git rev-parse --abbrev-ref HEAD",
        run_id="run-1",
        workdir=session.repo_path,
    )
    assert branch.exit_code == 0
    assert branch.stdout.strip() == "main"

    touch = manager.run_command(
        "echo 'hello' > sandbox_file.txt",
        run_id="run-1",
        workdir=session.repo_path,
    )
    assert touch.exit_code == 0
    assert (session.repo_path / "sandbox_file.txt").exists()

    manager.teardown("run-1")
    with pytest.raises(KeyError):
        manager.run_command("pwd", run_id="run-1")
