# Role: Senior QA Architect

# Objective: Build the Automated Reviewer and Janitor

We need to ensure that the code produced by the "Worker Agents" is safe and follows conventions before a human sees it.

## Task

Write the code for the Governance layer in `agents/governance/`.

1. **The Reviewer Agent (`reviewer.py`):**
   - **Trigger:** Designed to run on a GitHub Pull Request webhook or a manual pointer to a PR.
   - **Logic:** - Fetches the `diff` of the PR.
     - Runs a "Policy Check" LLM prompt: "Does this code introduce security risks? Does it follow PEP8/ESLint?"
     - **Hallucination Check:** Parses `requirements.txt` / `package.json` changes. Verifies if new packages actually exist on PyPI/NPM (mock this verification with a simple HTTP check).
   - **Action:** Post a comment on the PR (Approved/Request Changes).

2. **The Janitor Agent (`janitor.py`):**
   - **Task:** A specialized worker that runs on a schedule.
   - **Capability:** Scans `package.json` or `pyproject.toml` for outdated dependencies.
   - **Action:** Creates a branch, bumps the version, runs the test suite (via `SandboxManager`), and creates a PR if green.

**Output:**

- Python code for the Reviewer and Janitor agents.
