# Implementation Backlog: Harness-First Software Factory (v2)

**Date:** 2026-02-16  
**Scope:** Convert the v2 harness-first architecture into executable engineering tickets.  
**Primary Outcome:** Reliable control plane that keeps external agent harnesses running on backlog work with safety, auditability, and measurable quality.

---

## 1. Delivery Rules

### Definition of Ready (DoR)

A ticket is ready when:
1. It has a clear owner and target milestone.
2. Dependencies are resolved or explicitly tracked.
3. Acceptance criteria are testable and unambiguous.
4. Required secrets/services are available in the target environment.

### Definition of Done (DoD)

A ticket is done when:
1. Code is merged to default branch.
2. Automated tests for the ticket scope pass in CI.
3. Observability hooks (logs/metrics/traces) are added where applicable.
4. Runbook/docs are updated for operator-facing changes.
5. Acceptance criteria are verified and linked in PR notes.

---

## 2. Milestones and Exit Gates

### Milestone M0: Control Plane Foundations

Exit gate:
1. Canonical ticket/run state machine implemented.
2. Lease-based claims prevent duplicate execution.
3. Durable storage and queue are running in local/CI environments.

### Milestone M1: Single-Harness Execution MVP

Exit gate:
1. One harness (`codex`) can complete ticket -> PR in sandbox.
2. Budget and timeout enforcement is operational.
3. Human approval gate blocks autonomous PR creation for medium/high risk tasks.

### Milestone M2: Discovery + Governance

Exit gate:
1. Discovery services generate deduplicated, actionable tickets.
2. Governance runs deterministic checks and posts structured PR results.
3. Dead-letter and retry flows are stable under fault injection.

### Milestone M3: Multi-Harness + Production Hardening

Exit gate:
1. At least two harnesses are routable via adapters.
2. SLO dashboards and alerts are live.
3. Security controls (secrets, credentials, protected branches, kill switch) validated.

---

## 3. Ticket Backlog

## M0: Control Plane Foundations

### SF-001: Repository and Service Skeleton
**Type:** platform  
**Priority:** P0  
**Dependencies:** none  
**Deliverables:** base Python package layout (`core/`, `services/`, `infrastructure/`), lint/test tooling, Makefile tasks.

**Acceptance Criteria**
1. `make test`, `make lint`, and `make typecheck` run successfully on a fresh clone.
2. Project structure matches v2 design (`core/backlog`, `core/adapters`, `core/supervisor`, `core/sandbox`, `services/discovery`, `services/execution`, `services/governance`).
3. CI pipeline runs lint + tests on pull requests.

### SF-002: Canonical Domain Schemas
**Type:** backend  
**Priority:** P0  
**Dependencies:** SF-001  
**Deliverables:** versioned schemas/models for `Ticket`, `Run`, `Lease`, `Artifact`, `PolicyReport`.

**Acceptance Criteria**
1. JSON schema artifacts are committed for each domain model.
2. Validation rejects malformed payloads with explicit field-level errors.
3. Backward-compatible versioning strategy is documented with at least one migration example.

### SF-003: Database and Migration Layer
**Type:** backend  
**Priority:** P0  
**Dependencies:** SF-001, SF-002  
**Deliverables:** Postgres schema + migrations for tickets, runs, leases, run events, artifacts.

**Acceptance Criteria**
1. `make db-migrate` creates all required tables and indexes in an empty database.
2. Rollback/redo of the latest migration succeeds without manual SQL edits.
3. Uniqueness constraints enforce idempotency keys and run IDs.

### SF-004: Backlog Service Interface + Storage Adapter
**Type:** backend  
**Priority:** P0  
**Dependencies:** SF-002, SF-003  
**Deliverables:** `BacklogInterface` and concrete adapter with `fetch_ready`, `claim_ticket`, `heartbeat`, `complete_ticket`, `fail_ticket`, `create_ticket`.

**Acceptance Criteria**
1. Backlog API supports create/fetch/claim/heartbeat/complete/fail operations.
2. Unit tests cover success and conflict paths for each method.
3. Claim attempts on already leased tickets return deterministic conflict responses.

### SF-005: Lease and Idempotency Engine
**Type:** backend  
**Priority:** P0  
**Dependencies:** SF-004  
**Deliverables:** lease TTL handling, heartbeat renewal, idempotent create/update semantics.

**Acceptance Criteria**
1. Expired leases are reclaimable after configured TTL.
2. Duplicate ticket creation with same idempotency key does not create extra rows.
3. Concurrency test with 20 parallel claimers results in exactly one successful claim per ticket.

### SF-006: Queue and Dispatch Plumbing
**Type:** backend  
**Priority:** P0  
**Dependencies:** SF-003, SF-004  
**Deliverables:** queue abstraction (Redis-backed), dispatch enqueue/dequeue, dead-letter queue primitives.

**Acceptance Criteria**
1. Tickets can be enqueued/dequeued with visibility timeout semantics.
2. Failed jobs exceeding retry threshold are moved to dead-letter queue.
3. Queue health metrics (depth, age, retries) are exported.

### SF-007: Run State Machine and Supervisor Core
**Type:** backend  
**Priority:** P0  
**Dependencies:** SF-004, SF-006  
**Deliverables:** `RunSupervisor` with `dispatch`, `monitor_run`, `enforce_limits`, `recover_stale_runs`.

**Acceptance Criteria**
1. Allowed run transitions are enforced (`claimed -> running -> succeeded|failed|timed_out|canceled`).
2. Invalid state transitions are rejected and logged with reason.
3. Recovery job reclaims stale runs and updates status without data loss.

### SF-008: Structured Logging and Metrics Baseline
**Type:** observability  
**Priority:** P1  
**Dependencies:** SF-004, SF-007  
**Deliverables:** structured logs, correlation IDs, Prometheus/OpenTelemetry counters and timers.

**Acceptance Criteria**
1. Every run event log includes `run_id`, `ticket_id`, `harness`, and `state`.
2. Metrics include at minimum: run duration, success/failure counts, retry counts, queue latency.
3. A local dashboard shows end-to-end run throughput and failure rate.

### SF-009: Control Plane API
**Type:** backend  
**Priority:** P1  
**Dependencies:** SF-004, SF-007  
**Deliverables:** API endpoints for ticket CRUD, run lookup, lease introspection, pause/resume controls.

**Acceptance Criteria**
1. API auth is required for mutating endpoints.
2. `/health` and `/ready` endpoints reflect queue/db dependency status.
3. Pause/resume control prevents new dispatch while allowing active runs to finish.

### SF-010: Local Compose Stack
**Type:** infra  
**Priority:** P1  
**Dependencies:** SF-003, SF-006, SF-009  
**Deliverables:** `docker-compose.yml` for manager, runner, redis, postgres, webhook service.

**Acceptance Criteria**
1. `docker compose up` boots all core services locally with one command.
2. Manager can reach queue and database and pass readiness checks.
3. Runner runs with isolated privileges from manager.

## M1: Single-Harness Execution MVP

### SF-011: SandboxManager Provisioning Lifecycle
**Type:** infra  
**Priority:** P0  
**Dependencies:** SF-010  
**Deliverables:** `SandboxManager.provision`, `run_command`, `teardown` with artifact capture.

**Acceptance Criteria**
1. Provision clones repository and checks out target branch inside sandbox.
2. Command execution returns structured stdout/stderr/exit-code.
3. Teardown always runs and persists logs/artifacts for success and failure paths.

### SF-012: Workspace Persistence and Git Provenance
**Type:** infra  
**Priority:** P0  
**Dependencies:** SF-011  
**Deliverables:** branch/patch persistence strategy, commit attribution, reproducible workspace metadata.

**Acceptance Criteria**
1. Every run produces either a branch push or a patch artifact.
2. Commit metadata includes bot identity and run reference.
3. Replaying a stored patch in clean checkout reproduces resulting file changes.

### SF-013: AgentAdapter Contract and Codex Adapter
**Type:** backend  
**Priority:** P0  
**Dependencies:** SF-002, SF-011  
**Deliverables:** `AgentAdapter` interface and first concrete adapter for `codex`.

**Acceptance Criteria**
1. Adapter supports launch, event stream, control signal, artifact collection, termination.
2. Supervisor can execute at least one complete ticket through the adapter.
3. Adapter emits normalized event schema consumed by run ledger.

### SF-014: Execution Runner Workflow
**Type:** backend  
**Priority:** P0  
**Dependencies:** SF-007, SF-011, SF-013  
**Deliverables:** `ClaimTicket -> ProvisionSandbox -> LaunchHarness -> Monitor -> Validate -> SubmitPR -> Finalize`.

**Acceptance Criteria**
1. Runner claims exactly one ticket lease before execution.
2. Validation step executes configured test/lint commands in sandbox.
3. Successful run opens or updates a PR and marks ticket complete.

### SF-015: Budget, Timeout, and Stuck-Run Enforcement
**Type:** backend  
**Priority:** P0  
**Dependencies:** SF-014  
**Deliverables:** per-run limits for wall-clock time, token budget, inactivity heartbeat timeout.

**Acceptance Criteria**
1. Exceeding any configured budget terminates run with explicit terminal status.
2. Stuck runs (no heartbeat/events) are canceled and re-queued or failed by policy.
3. Budget termination emits clear audit event and operator alert.

### SF-016: PR Integration and Evidence Packaging
**Type:** backend  
**Priority:** P1  
**Dependencies:** SF-012, SF-014  
**Deliverables:** PR creation/update client, evidence bundle links (logs, test output, diff summary).

**Acceptance Criteria**
1. PR description includes ticket ID, run ID, and acceptance criteria checklist.
2. Evidence bundle is accessible from PR comment/body.
3. Duplicate PR creation is prevented for same run/ticket pair.

### SF-017: Retry Policy and Dead-Letter Workflow
**Type:** backend  
**Priority:** P1  
**Dependencies:** SF-006, SF-014  
**Deliverables:** retry classifier, exponential backoff policy, dead-letter queue consumer.

**Acceptance Criteria**
1. Transient failures are retried with bounded exponential backoff.
2. Non-retriable failures are dead-lettered immediately with reason code.
3. Dead-letter inspector endpoint lists failure class and remediation hints.

### SF-018: Human Approval Gate (MVP Safety)
**Type:** governance  
**Priority:** P1  
**Dependencies:** SF-016  
**Deliverables:** policy gate requiring human approval before PR open for selected ticket classes.

**Acceptance Criteria**
1. Configurable rules determine which tickets require approval.
2. Blocked runs remain in `awaiting_approval` until explicit action is taken.
3. Approved runs continue without manual restart or state corruption.

## M2: Discovery and Governance

### SF-019: Incident Ingestor Service
**Type:** discovery  
**Priority:** P1  
**Dependencies:** SF-004  
**Deliverables:** ingestion pipeline for mock/real incident stream with signature grouping and thresholds.

**Acceptance Criteria**
1. Incidents are grouped by deterministic signature and release/environment dimensions.
2. Threshold and cooldown policy prevent duplicate ticket spam.
3. Created tickets contain evidence payload and idempotency key.

### SF-020: Coverage Gap Scanner
**Type:** discovery  
**Priority:** P1  
**Dependencies:** SF-011, SF-004  
**Deliverables:** scanner that runs coverage and creates prioritized test-gap tickets.

**Acceptance Criteria**
1. Coverage scanner runs in sandbox and parses report output reliably.
2. Ticket payload includes module path, current coverage, target coverage, acceptance criteria.
3. Scanner ignores modules excluded by policy file.

### SF-021: Discovery Scheduler and Dedupe Registry
**Type:** discovery  
**Priority:** P1  
**Dependencies:** SF-019, SF-020  
**Deliverables:** cron-compatible dispatcher and dedupe registry for repeated findings.

**Acceptance Criteria**
1. Both discovery services run on configured cadence (default every 4 hours).
2. Repeated findings within suppression window update existing ticket instead of creating new one.
3. Scheduler records run outcome metrics and errors.

### SF-022: Governance Gatekeeper Pipeline
**Type:** governance  
**Priority:** P0  
**Dependencies:** SF-016  
**Deliverables:** deterministic checks for lint, tests, SAST, dependency/license policy.

**Acceptance Criteria**
1. Gatekeeper runs check suite on PR events and stores per-check outcomes.
2. Failing mandatory checks set PR status to request changes.
3. Governance result is reproducible via documented command bundle.

### SF-023: Dependency Integrity Validator
**Type:** governance  
**Priority:** P1  
**Dependencies:** SF-022  
**Deliverables:** validator for introduced package names/versions against registry metadata and policy.

**Acceptance Criteria**
1. Validator detects nonexistent packages and disallowed versions.
2. Validator enforces license allow/deny rules.
3. Findings are posted with package-level evidence and remediation hints.

### SF-024: Structured PR Policy Reporter
**Type:** governance  
**Priority:** P1  
**Dependencies:** SF-022, SF-023  
**Deliverables:** standardized PR comment/report format with rule IDs, status, links to evidence.

**Acceptance Criteria**
1. One consolidated report comment is maintained per PR (updated, not spammed).
2. Report includes pass/fail summary and top blocking issues.
3. Report links to raw logs/artifacts for each failed rule.

### SF-025: Janitor Service for Dependency Updates
**Type:** governance  
**Priority:** P2  
**Dependencies:** SF-011, SF-022  
**Deliverables:** scheduled low-risk dependency updater with policy filters.

**Acceptance Criteria**
1. Janitor only updates dependencies allowed by policy.
2. Each candidate update runs tests before PR creation.
3. Failed updates are skipped with explicit reason logging.

## M3: Multi-Harness and Production Hardening

### SF-026: Claude Code Adapter
**Type:** adapters  
**Priority:** P1  
**Dependencies:** SF-013  
**Deliverables:** `claude_code` adapter implementing full `AgentAdapter` contract.

**Acceptance Criteria**
1. Adapter passes shared adapter conformance test suite.
2. Supervisor can route eligible tickets to `claude_code`.
3. Event stream normalization matches canonical run event schema.

### SF-027: Gemini CLI Adapter
**Type:** adapters  
**Priority:** P1  
**Dependencies:** SF-013  
**Deliverables:** `gemini_cli` adapter implementing full `AgentAdapter` contract.

**Acceptance Criteria**
1. Adapter passes shared adapter conformance test suite.
2. Supervisor can route eligible tickets to `gemini_cli`.
3. Adapter failure modes map to standard retry/non-retry classes.

### SF-028: OpenHands Adapter (Optional Lane)
**Type:** adapters  
**Priority:** P2  
**Dependencies:** SF-013  
**Deliverables:** `openhands` adapter behind feature flag.

**Acceptance Criteria**
1. Adapter can be enabled/disabled per environment via config.
2. Supervisor excludes disabled adapters from routing decisions.
3. Adapter emits same normalized run/artifact data model as other harnesses.

### SF-029: Routing Policy Engine
**Type:** backend  
**Priority:** P1  
**Dependencies:** SF-026, SF-027  
**Deliverables:** policy for harness selection based on repo language, ticket type, cost budget, past success rates.

**Acceptance Criteria**
1. Routing decisions are deterministic for identical inputs.
2. Policy logs selected harness and scored alternatives.
3. Fallback routing activates when preferred harness is unhealthy/unavailable.

### SF-030: Secrets and Identity Hardening
**Type:** security  
**Priority:** P0  
**Dependencies:** SF-010, SF-014  
**Deliverables:** secret manager integration, short-lived credentials, bot-scoped permissions, protected branch enforcement.

**Acceptance Criteria**
1. No long-lived plaintext credentials remain in env files for non-local environments.
2. Service accounts cannot push directly to protected branches.
3. Secret access and usage are auditable by run/service identity.

### SF-031: Network and Runtime Isolation Policies
**Type:** security  
**Priority:** P1  
**Dependencies:** SF-011, SF-030  
**Deliverables:** egress restrictions, runtime seccomp/capability policies, resource quotas for runner workloads.

**Acceptance Criteria**
1. Runner workloads execute as non-root with configured CPU/memory limits.
2. Egress policy blocks disallowed domains and records blocked attempts.
3. Policy regression tests verify expected allow/deny behavior.

### SF-032: SLO Dashboards and Alerting
**Type:** observability  
**Priority:** P1  
**Dependencies:** SF-008, SF-022  
**Deliverables:** dashboards and alerts for reliability, quality, and cost KPIs.

**Acceptance Criteria**
1. Dashboards show at minimum: success rate, P95 run duration, dead-letter rate, cost per merged PR.
2. Alerts fire for stuck runs, retry storms, queue backlog growth, governance failure spikes.
3. Alert runbooks include triage steps and rollback/kill-switch actions.

### SF-033: Kill Switch and Safe Degradation Controls
**Type:** platform  
**Priority:** P0  
**Dependencies:** SF-009, SF-032  
**Deliverables:** global pause, per-repo pause, per-harness disable, read-only governance mode.

**Acceptance Criteria**
1. Global pause stops new dispatch within 30 seconds.
2. In-flight runs can be allowed to drain or canceled by policy.
3. Operator actions are logged with actor identity and timestamp.

### SF-034: Canary Rollout and Pilot Validation
**Type:** release  
**Priority:** P1  
**Dependencies:** SF-029, SF-030, SF-031, SF-032, SF-033  
**Deliverables:** phased rollout plan and pilot report for one target repo.

**Acceptance Criteria**
1. Pilot runs for a minimum 2-week window with agreed risk limits.
2. Exit metrics meet thresholds for promotion (quality, reliability, cost).
3. Post-pilot report documents incidents, corrective actions, and go/no-go decision.

---

## 4. Initial KPI Targets (for M3 Go/No-Go)

1. PR acceptance rate (without major rework) >= 60%.
2. Duplicate ticket rate <= 3%.
3. Dead-letter rate <= 5% of dispatched runs.
4. Median cycle time (ticket claim to PR open) <= 90 minutes.
5. Escaped policy violations after merge = 0 for critical severity.

---

## 5. Suggested First Sprint Cut (2 Weeks)

1. SF-001 Repository and Service Skeleton
2. SF-002 Canonical Domain Schemas
3. SF-003 Database and Migration Layer
4. SF-004 Backlog Service Interface + Storage Adapter
5. SF-005 Lease and Idempotency Engine
6. SF-007 Run State Machine and Supervisor Core
7. SF-010 Local Compose Stack

This sprint establishes the minimum reliable substrate before sandbox and adapter work begins.

---

## 6. Concept Exit Standard

Program completion must satisfy the concept-level Definition of Done in:

`/Users/jacbaile/Workspace/ventures/ai/software-factory/docs/07-concept-success-criteria.md`

Milestone completion alone is not sufficient for claiming the original concept has been achieved.
