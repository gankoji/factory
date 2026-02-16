# Concept Success Criteria: Program Definition of Done

**Date:** 2026-02-16  
**Purpose:** Define what “we achieved the original concept” means in pass/fail terms, not just long-term observability metrics.

---

## 1. Concept to Validate

The project is done only when it proves this statement in production-like conditions:

`A harness-first control plane can continuously discover, execute, and govern software work with minimal human intervention, while remaining safe, auditable, and economically viable.`

---

## 2. Program-Level Definition of Done (All Must Pass)

| ID | Success Criterion | Done When | Required Evidence | Validation Exercise |
|---|---|---|---|---|
| C1 | Continuous autonomous operation | System runs for 14 consecutive days with no manual restarts and no uncontrolled outage longer than 15 minutes. | Uptime log, incident timeline, restart history. | 14-day unattended pilot run. |
| C2 | Backlog self-sufficiency | Ready queue remains above minimum target for 95% of pilot hours, without duplicate-ticket storming. | Queue depth history, dedupe report, ticket source mix. | Pilot run with discovery enabled and synthetic incident feed spikes. |
| C3 | End-to-end ticket execution | At least 50 tickets complete full lifecycle (claim -> sandbox -> PR -> governance decision) with traceable state transitions. | Run ledger exports, PR links, state transition audit. | Controlled benchmark batch across bug/test/chore tickets. |
| C4 | Quality gate effectiveness | No PR with critical policy violations is merged through automated lanes. | Governance reports, merge logs, exception log. | Inject known failing policies into test PRs and verify blocks. |
| C5 | Sandbox safety boundaries | No run can write outside approved workspace or bypass protected branch policy. | Security test report, branch protection audit, filesystem policy test output. | Red-team style sandbox escape and branch bypass tests. |
| C6 | Reproducibility and auditability | Every merged PR has run ID, artifact bundle, and replayable patch/branch provenance. | Artifact manifest, replay test report, commit metadata samples. | Random replay audit on 10 merged PRs. |
| C7 | Multi-harness operability | At least two harnesses pass adapter conformance and complete the same reference ticket set. | Adapter conformance test results, comparative run report. | Harness swap drill on shared benchmark tickets. |
| C8 | Recovery and resilience | Stuck runs, worker crashes, and queue faults recover automatically within policy limits. | Fault injection report, MTTR summary, dead-letter audit. | Game day with runner kill, queue latency spike, and DB failover simulation. |
| C9 | Human control and override | Operators can pause globally, pause per repo, cancel specific runs, and safely resume without data corruption. | Control action logs, before/after state snapshots. | Live operations drill with scripted control commands. |
| C10 | Economic viability | Cost per merged PR and success-adjusted throughput beat agreed baseline from current human-only process. | Cost ledger, throughput comparison, baseline doc. | Pilot outcome review versus pre-project baseline. |

---

## 3. Non-Negotiable Artifacts for Concept Sign-Off

The concept is not done unless all artifacts exist and are reviewable:

1. Pilot report (14-day unattended run).
2. Fault-injection/game-day report.
3. Security boundary validation report.
4. Governance effectiveness report with blocked negative tests.
5. Reproducibility audit pack (sampled merged PRs).
6. Cost and throughput comparison against baseline.
7. Operator runbook and escalation playbook.

---

## 4. Milestone Exit Mapping

Use this mapping to avoid claiming success prematurely:

1. M0 must satisfy prerequisites for C6 and C8 (state, leases, audit basics).
2. M1 must satisfy prerequisites for C3, C5, and partial C9.
3. M2 must satisfy prerequisites for C2 and C4.
4. M3 must satisfy C1 through C10 in full and produce all sign-off artifacts.

---

## 5. Final Sign-Off Checklist

Mark each as `PASS` or `FAIL` with link to evidence:

1. C1 Continuous autonomous operation.
2. C2 Backlog self-sufficiency.
3. C3 End-to-end ticket execution.
4. C4 Quality gate effectiveness.
5. C5 Sandbox safety boundaries.
6. C6 Reproducibility and auditability.
7. C7 Multi-harness operability.
8. C8 Recovery and resilience.
9. C9 Human control and override.
10. C10 Economic viability.

Program status is `DONE` only when all ten criteria are `PASS`.
