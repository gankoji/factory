# Role: Senior Systems Engineer

# Objective: Build the Ephemeral Execution Sandbox

We need a safe environment for our "Worker Agents" to write and test code without destroying the host machine.

## Context

We have a `/core` library (from the previous step). Now we need the "Factory Floor."

## Task

Design and write the code for the **Execution Sandbox**.

1. **The Dockerfile:** Create a versatile `Dockerfile` in `infrastructure/docker/` that:
   - Inherits from a slim Python or Node base (depending on target repo).
   - Installs git, common build tools, and the CLI tools for our stack.
   - Sets up a non-root user for the agent to run as.
2. **The Sandbox Controller (`core/sandbox.py`):**
   - Write a Python class `SandboxManager` that wraps the Docker SDK.
   - Method `spin_up(repo_url, branch)`: Starts a container, clones the repo, and checks out the branch.
   - Method `run_command(cmd)`: Executes a shell command inside the container and returns `stdout`/`stderr`.
   - Method `teardown()`: Destroys the container.
   - **Crucial:** Ensure the container has volume mounts or mechanisms to persist the code changes back to the host or push them to remote.

3. **The Worker Agent Logic (`agents/execution/worker.py`):**
   - Use LangGraph to define a graph for a "Coding Agent."
   - **Nodes:** `ReadTicket` -> `PlanChanges` -> `WriteCode` (using Sandbox) -> `RunTests` (using Sandbox) -> `SubmitPR`.
   - **Constraint:** The agent _must_ use the `SandboxManager` for all file edits and test runs. It cannot run code locally.

**Output:**

- The Dockerfile.
- The Python code for `SandboxManager` and the LangGraph `worker.py`.
