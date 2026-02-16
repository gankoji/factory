# High-Level Design: Harness-First Autonomous Software Factory

**Version:** 2.0
**Status:** DRAFT
**Architectural Pattern:** Adapter-Driven Control Plane with Asynchronous Service Loops

---

## 1. Executive Summary

This system is a **manager-of-harnesses**, not a builder of custom coding agents.

Instead of implementing agent cognition in LangGraph (or similar), we run best-in-class external agent harnesses (Codex CLI, Claude Code, Gemini CLI, OpenHands) inside controlled sandboxes. The platform's value is in backlog quality, orchestration reliability, safety guardrails, and governance evidence.

---

## 2. Design Thesis

1. **Buy agent intelligence, build control plane discipline:** Reuse mature agent harnesses and focus internal effort on scheduling, isolation, policy, and observability.
2. **Adapter-first architecture:** Every harness is integrated through a common `AgentAdapter` contract.
3. **Deterministic before probabilistic:** Prefer deterministic checks for policy/security; use LLM judgments as secondary signal.
4. **Progressive autonomy:** Increase automation only after objective reliability and quality metrics are met.

---

## 3. Core Architecture: The Tri-Loop (Reframed)

### Loop 1: Discovery and Backlog Curation

- **Objective:** Keep a high-quality queue of actionable tasks.
- **Services:** Incident ingestor, coverage scanner, dependency monitor.
- **Controls:** Deduplication, confidence scoring, suppression windows, priority policy.
- **Output:** Normalized tickets with acceptance criteria and idempotency keys.

### Loop 2: Execution Supervision

- **Objective:** Keep many harness instances running productively and safely.
- **Services:** Dispatcher, sandbox manager, run supervisor, harness adapters.
- **Mechanism:** Each ticket is claimed, assigned to a compatible harness, executed in an ephemeral sandbox, and tracked with heartbeats/timeouts.
- **Output:** Branch/patch + run evidence + PR URL.

### Loop 3: Governance and Maintenance

- **Objective:** Enforce quality and safety gates before merge.
- **Services:** Deterministic gatekeeper, optional LLM reviewer, dependency janitor.
- **Mechanism:** Evaluate PRs against explicit policy checks and attach evidence.
- **Output:** Structured pass/fail decisions with reproducible artifacts.

---

## 4. Control Plane Components

### 4.1 Backlog Service

- Canonical ticket schema and lifecycle state machine.
- Lease-based claim protocol to prevent duplicate execution.
- Priority queue with starvation prevention.

### 4.2 Agent Adapter Layer

- Unified interface across harnesses (`codex`, `claude_code`, `gemini_cli`, `openhands`).
- Capability metadata: language support, tool availability, max concurrency, cost profile.
- Session controls: launch, stream events, nudge, cancel, terminate.

### 4.3 Sandbox and Workspace Service

- Ephemeral workspace provisioning per run.
- Resource limits (CPU/memory/time budget) and constrained networking.
- Artifact collection (patches, logs, test outputs, trace links).

### 4.4 Governance Pipeline

- Deterministic checks: lint, tests, SAST, dependency/license policy.
- Optional LLM reviewer for architectural/style feedback.
- Single policy report posted to PR.

### 4.5 Observability and Audit

- Run ledger for every state transition and command outcome.
- Metrics: ticket usefulness, rerun rate, PR acceptance rate, MTTR, cost per merged PR.
- Alerts: stuck runs, retry storms, policy failures, budget overruns.

---

## 5. Canonical Data Contracts

### 5.1 Ticket

```json
{
  "id": "ENG-1042",
  "source": "sentry|coverage|human",
  "type": "bug|test-gap|chore",
  "priority": "low|medium|high|critical",
  "repo": "frontend-monorepo",
  "context": {
    "filepaths": ["src/components/Header.tsx"],
    "error_signature": "TypeError: undefined is not a function"
  },
  "acceptance_criteria": [
    "All unit tests pass",
    "No new lint violations"
  ],
  "idempotency_key": "sha256:..."
}
```

### 5.2 Run

```json
{
  "run_id": "run_01J...",
  "ticket_id": "ENG-1042",
  "harness": "codex",
  "state": "claimed|running|blocked|succeeded|failed|timed_out|canceled",
  "sandbox_id": "sbx_...",
  "budget": {
    "max_minutes": 45,
    "max_tokens": 120000
  },
  "artifacts": {
    "pr_url": "https://github.com/org/repo/pull/123",
    "logs": "s3://.../run.log"
  }
}
```

---

## 6. Task Lifecycle

1. Discovery creates/updates a normalized ticket.
2. Dispatcher claims ticket with a lease and idempotency guard.
3. Supervisor selects harness via adapter capability and policy.
4. Sandbox manager provisions isolated workspace.
5. Adapter launches harness session and streams events.
6. Supervisor enforces heartbeat/time/token/runtime budgets.
7. On completion, artifacts are collected and PR is opened/updated.
8. Governance checks run and publish a policy report.
9. Ticket is completed, retried, or dead-lettered.

---

## 7. Security and Safety Model

- Worker workloads run as non-root with strict resource limits.
- Protected branch rules and bot-scoped credentials are mandatory.
- Secrets sourced from managed secret stores; short-lived tokens preferred.
- Network egress restricted to approved domains where feasible.
- Circuit breakers halt automation on elevated failure or risk signals.

---

## 8. Deployment Topology

- `manager`: control plane API + scheduler + dispatcher.
- `runner`: sandbox execution host (can be one pool or many).
- `queue`: Redis/Postgres-backed job and lease state.
- `db`: persistent metadata and run ledger.
- `webhook`: PR and governance event intake.

The manager should not require broad host privileges. Privileged runtime access is isolated to runner infrastructure.

---

## 9. Rollout Plan

1. **Phase 0:** Single repo, one harness, human approval before PR open.
2. **Phase 1:** Multi-harness routing, deterministic governance mandatory.
3. **Phase 2:** Auto-open PRs for low-risk classes (tests/chore only).
4. **Phase 3:** Controlled auto-merge for pre-approved policy lanes.

Advancement requires meeting SLOs and quality/cost thresholds.

---

## 10. Explicit Non-Goals

- Building a bespoke planning/coding/review agent framework.
- Replacing external harness cognition with internal LangGraph loops.
- Full autonomy without enforceable safety, audit, and rollback controls.
