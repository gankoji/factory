# Role: Senior Systems Engineer

# Objective: Build the Harness Execution Sandbox

We need a safe environment for external agent harnesses to write and test code without harming the host machine.

## Context

We have a `/core` library from the previous step. Now we need a sandbox runner that can execute harness sessions in isolation.

## Task

Design and write the code for the **Execution Sandbox**.

1. **The Dockerfile:** Create a versatile `Dockerfile` in `infrastructure/docker/` that:
   - Uses a slim Python base and installs git + common build tools.
   - Supports installation of selected harness CLIs via build args or optional layers.
   - Runs as a non-root user.
   - Mounts a workspace directory for repo checkout and artifacts.
2. **The Sandbox Controller (`core/sandbox.py`):**
   - Write a `SandboxManager` class wrapping the Docker SDK.
   - Method `provision(repo_url, branch, run_id)`: Starts a container, clones the repo, and checks out the branch.
   - Method `run_command(cmd)`: Executes a shell command inside the container and returns `stdout`/`stderr`.
   - Method `run_harness(adapter, task_payload)`: Launches a harness task inside the container.
   - Method `teardown()`: Destroys the container and captures logs/artifacts.
   - **Crucial:** Ensure code changes persist through branch pushes or exported patches; no host-side file edits/tests.
3. **The Execution Runner (`services/execution/runner.py`):**
   - Build a run workflow: `ClaimTicket -> ProvisionSandbox -> LaunchHarness -> Monitor -> Validate -> SubmitPR -> Finalize`.
   - The runner must use `SandboxManager` for all edits and test runs.
   - Add runtime/time/token budget enforcement and stuck-run detection.

**Output:**

- The Dockerfile.
- Python code for `SandboxManager` and `runner.py`.
