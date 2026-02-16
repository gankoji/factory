# Role: Senior QA Architect

# Objective: Build Deterministic Governance and Maintenance Services

We need strong quality gates for code produced by external harnesses before humans review merges.

## Task

Write code for governance services in `services/governance/`.

1. **The Gatekeeper (`gatekeeper.py`):**
   - **Trigger:** GitHub PR webhook or manual PR pointer.
   - **Logic:**
     - Fetch PR diff.
     - Run deterministic checks (lint, tests, security scan, dependency/license checks).
     - Optional: run a read-only LLM/harness review as secondary signal.
     - **Dependency integrity check:** Validate introduced packages and versions against registry metadata (not only name existence).
   - **Action:** Post a structured PR comment with rule IDs, pass/fail status, and evidence links.

2. **The Janitor (`janitor.py`):**
   - **Task:** Scheduled dependency maintenance.
   - **Capability:** Scan lockfiles/manifests for outdated dependencies under policy (allowlisted ecosystems, semver constraints).
   - **Action:** Create branch, apply updates, run tests via `SandboxManager`, and open PR only when checks pass.

**Output:**

- Python code for `gatekeeper.py` and `janitor.py`.
