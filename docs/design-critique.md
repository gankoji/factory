# Critique: 24/7 Autonomous Software Factory Design

## Revision Note (2026-02-16)

This critique was written against the pre-pivot design that leaned toward custom agent implementation.
The current `design-doc.md` has been updated to a harness-first architecture (Codex/Claude/Gemini/OpenHands via adapters), which directly addresses a major strategic concern raised here.

## Overall Assessment

The design is directionally strong and shows good systems thinking, but it is currently **concept-complete and execution-incomplete**.  
The Tri-Loop model is a solid organizing principle, yet the plan needs stronger guarantees around orchestration durability, security boundaries, ticket quality control, and production operations before it can safely run unattended.

## What Is Working Well

1. **Clear loop separation:** Discovery, Execution, and Governance are logically decomposed and easy to reason about.
2. **Sandbox-first execution model:** Treating code changes as ephemeral workloads is the right default.
3. **Interface-driven intent:** Defining `TicketInterface`, `GitInterface`, and an LLM abstraction is a good foundation for portability.
4. **Governance as a first-class loop:** Quality and policy checks are included early instead of treated as an afterthought.
5. **Operational narratives:** Night Shift and Janitor protocols help validate expected behavior end-to-end.

## Concept-Level Gaps

1. **Value function is underspecified:** “Generate tickets continuously” is not enough; the system needs explicit ranking goals (risk reduction, incident frequency, cycle-time impact, coverage gain per LOC).
2. **Autonomy target is too absolute:** “24/7 autonomous” should be staged by risk tier. Full autonomy without progressive guardrails will create operational and trust issues.
3. **Backlog quality controls are missing:** Discovery agents can flood low-value or duplicate work without confidence scoring and suppression windows.

## Architecture-Level Gaps

1. **No durable event backbone:** Current `while True` + polling/thread pool design is fragile; crashes can lose state and duplicate work.
2. **No explicit lifecycle state machine:** Ticket/PR transitions and ownership leases are not formally defined.
3. **Idempotency is not addressed:** Retries across discovery/execution/governance can create duplicate tickets, branches, and comments.
4. **Interface mismatch risk:** Doc 01 defines `fetch_backlog`, while Doc 05 uses `fetch_ready_tickets`; contract drift is already visible.
5. **LangGraph boundaries are unclear:** Graph logic is requested, but persistent memory, checkpointing, and recovery semantics are unspecified.

## Execution/Sandbox Critique

1. **Docker socket exposure is high risk:** Mounting `/var/run/docker.sock` into the manager grants near-root control of host Docker.
2. **Isolation policy is conceptual, not enforceable yet:** Egress allowlists are mentioned, but concrete enforcement (network policy, DNS controls) is not defined.
3. **Persistence model is ambiguous:** “Volume mounts or push to remote” needs a single authoritative path for provenance and rollback.
4. **Resource budgets are missing:** No hard CPU/memory/runtime/tooling limits per worker ticket.
5. **Toolchain portability is underdefined:** “Slim Python or Node base” is too generic for deterministic multi-repo builds.

## Discovery Critique

1. **Heuristics are simplistic:** “>10 errors/hour” and “lowest coverage file” will often produce noisy or low-value work.
2. **No dedupe/root-cause handling:** Similar errors across services/releases can create ticket spam.
3. **No confidence/impact metadata:** Tickets need machine-generated confidence, blast radius, and expected value estimates.
4. **No suppression policy:** Repeated known failures need cooldown windows and “already assigned” checks.

## Governance Critique

1. **LLM-only policy checks are brittle:** Security/style checks should be layered with deterministic scanners (SAST, linters, dependency audit).
2. **Hallucination check is too weak:** Package existence HTTP checks do not validate package trust, version safety, typosquats, or licensing.
3. **PR decisioning needs evidence:** “Approve/Request Changes” should include rule IDs, failing checks, and reproducible command output.
4. **Janitor changes need tighter guardrails:** Automatic dependency updates require semver policy, allowlists, and rollback strategy.

## Operational Readiness Gaps

1. **No reliability model:** Missing retry policy, dead-letter queues, backoff strategy, and orphaned-worker cleanup.
2. **No observability spec:** Need structured logs, traces, per-loop SLIs/SLOs, and cost/token telemetry.
3. **No secret management strategy:** Environment variables are useful locally but insufficient for production rotation and scope control.
4. **No staged rollout plan:** Missing canary strategy, kill switches, and per-repo onboarding gates.
5. **No human override protocol:** Need explicit “pause loop”, “manual claim”, and “force close” controls.

## Execution Plan Critique (Docs 01-05)

1. **Good sequencing but incomplete milestones:** Steps 01-05 cover component generation, but skip architecture hardening and rollout operations.
2. **Prompt-first, contract-light:** The docs read as implementation prompts rather than an executable architecture spec with invariants.
3. **Cross-loop integration is weakly specified:** There is no canonical event schema or message bus contract between loops.
4. **Security is acknowledged but not encoded:** High-level safeguards are listed without concrete enforcement mechanisms.

## Recommended Path to Production

1. **Phase 0: Control Plane Foundations**
   - Define canonical state machine and event schema.
   - Add durable queue + idempotency keys + lease-based ticket claiming.
   - Add run ledger for every agent action (auditability).
2. **Phase 1: Constrained MVP**
   - Single language, single repo, one discovery signal, one worker.
   - Human approval required before branch push.
   - Success criteria: zero duplicate tickets, deterministic reruns, stable test pass rate.
3. **Phase 2: Safety Hardening**
   - Replace socket exposure model with safer execution isolation where possible.
   - Add deterministic policy checks (lint/SAST/dependency/license/SBOM).
   - Add budget controls (token/runtime/cost) and circuit breakers.
4. **Phase 3: Controlled Autonomy**
   - Gradually relax human gates by risk class.
   - Add confidence thresholds for auto-merge eligibility.
   - Expand to multi-repo only after SLO compliance over a fixed window.

## Priority Fixes Before Implementation Continues

1. Define and freeze loop contracts (events, states, idempotency, ownership).
2. Decide the secure execution model for worker isolation (do not defer this).
3. Replace polling-only orchestration with durable scheduling/queue semantics.
4. Establish governance as “LLM + deterministic checks,” not LLM alone.
5. Add measurable KPIs (ticket usefulness, PR acceptance rate, escaped defects, cost per merged PR).

## Bottom Line

The core concept is strong and likely viable, but the current plan is not production-safe yet.  
If the next iteration prioritizes **durability, security, and deterministic governance**, this can become a practical autonomous delivery platform rather than an impressive prototype.
