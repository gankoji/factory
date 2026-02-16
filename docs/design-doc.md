# High-Level Design: The 24/7 Autonomous Software Factory

**Version:** 1.0  
**Status:** DRAFT  
**Architectural Pattern:** Tiered Multi-Agent System (TMAS) with Asynchronous Loops

---

## 1. Executive Summary

This system transitions software development from a human-bottlenecked process to a **Manager-of-Agents** model. By implementing a "Tri-Loop" architecture, we decouple the _creation_ of work from the _execution_ of work, allowing a fleet of AI agents to operate 24/7 in parallel. The system utilizes ephemeral sandboxed environments for safety and a strict governance layer to maintain code quality.

---

## 2. Core Architecture: The Tri-Loop Model

The system is composed of three asynchronous, self-reinforcing loops.

### Loop 1: Discovery (The Backlog Engine)

- **Objective:** Prevent idle time by autonomously generating high-value maintenance and optimization tasks.
- **Agents:** \* **Log Miner:** Ingests observability data (Sentry/Datadog). Clusters recurring errors and generates bug reports.
  - **Coverage Analyst:** Scans the codebase for low-coverage modules and generates "Write Test" tickets.
  - **Dependency Watchdog:** Monitors `package.json`/`pyproject.toml` for deprecated or vulnerable packages.
- **Output:** Structured Tickets (Linear/Jira) tagged as `ready-for-robot`.

### Loop 2: Execution (The Factory Floor)

- **Objective:** Parallelize development without context switching or environment conflicts.
- **Agents:** \* **Worker Swarm:** A scalable fleet of coding agents.
- **Mechanism:**
  - **Ephemeral Sandboxes:** Every ticket spins up a fresh, isolated Docker container.
  - **Tooling:** Agents have CLI access to `git`, `grep`, `sed`, and language-specific linters.
- **Output:** A GitHub Pull Request (PR) with passing tests.

### Loop 3: Governance (The Quality Gate)

- **Objective:** Ensure no AI-generated code merges without passing strict quality and safety checks.
- **Agents:** \* **The Reviewer:** A read-only agent that critiques PR diffs against the "Style Guide" and "Architectural Vision."
  - **Hallucination Check:** Verifies that all introduced dependencies exist in public registries (npm/PyPI).
- **Output:** PR Comments (Request Changes) or Human Notification (Ready for Merge).

---

## 3. Technical Stack & Infrastructure

### 3.1 Orchestration Layer

- **Framework:** **LangGraph** (Python). Chosen for its ability to manage stateful, multi-turn agent workflows and cyclical graphs (Plan -> Code -> Error -> Fix).
- **LLM Provider:** Model-agnostic wrapper (defaulting to GPT-4o or Claude 3.5 Sonnet for coding, lighter models for triage).

### 3.2 Infrastructure Layer

- **Container Runtime:** **Docker** (Sibling/Sidecar pattern). The Orchestrator runs in a container and spawns sibling containers for Workers.
- **Communication:**
  - **Internal:** Shared Volume Mounts (for code persistence).
  - **External:** Linear API (Ticketing), GitHub API (VCS), Slack/Discord (Alerting).

### 3.3 Security & Isolation (The "Sandbox Protocol")

- **Network:** Worker containers have **egress-only** access to whitelisted domains (PyPI, npm, GitHub). No ingress.
- **Identity:** Agents operate under restricted Service Accounts (`ai-worker-bot`).
- **Constraints:**
  - `PROTECTED_BRANCHES`: Agents cannot push to `main` or `production`.
  - `MAX_BUDGET`: Token usage caps per ticket to prevent infinite loops.

---

## 4. Operational Workflows

### 4.1 The "Night Shift" Protocol (Unattended)

1. **18:00:** Human Manager approves a batch of 20 tickets in the `ready-for-robot` queue.
2. **19:00:** **Orchestrator** spins up 5 concurrent Worker Agents.
3. **19:05:** **Worker A** claims Ticket #101, spins up `sandbox-101`, clones repo.
4. **19:30:** **Worker A** runs tests. Tests fail. Agent reads `stderr`, refactors code, re-runs tests.
5. **20:00:** Tests pass. **Worker A** pushes branch `feat/101-fix` and opens PR. Container `sandbox-101` is destroyed.
6. **20:05:** **Reviewer Agent** scans PR. Finds missing Docstring. Comments on PR.
7. **20:10:** **Worker A** wakes up, reads comment, fixes Docstring, pushes update.
8. **08:00 (Next Day):** Human Manager reviews "Nightly Report" and merges valid PRs.

### 4.2 The "Janitor" Protocol (Scheduled)

- **Trigger:** Cron (Every Sunday at 02:00).
- **Action:** **Dependency Agent** creates a branch `chore/update-deps`.
- **Logic:** 1. `npm outdated` 2. For each package: `npm update [package]` -> `npm test`. 3. If Pass: Commit. If Fail: Revert and skip.
- **Result:** A clean PR with safely updated dependencies waiting for Monday morning.

---

## 5. Data Structures

### 5.1 The Standard Ticket Interface

Agents communicate via a standardized JSON schema, regardless of the underlying ticketing system (Jira/Linear).

```json
{
  "id": "ENG-1042",
  "type": "bug | feature | chore",
  "priority": "low | medium | high",
  "context": {
    "repo": "frontend-monorepo",
    "filepaths": ["src/components/Header.tsx"],
    "error_logs": "Traceback (most recent call last)..."
  },
  "acceptance_criteria": ["Unit tests pass", "No new React warnings in console"]
}
```
