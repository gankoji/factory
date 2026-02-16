# Role: Observability Engineer

# Objective: Create Backlog Discovery Services

We need enough high-quality work to keep harness runners productive 24/7.

## Task

Write code for two deterministic discovery services in `services/discovery/`.

1. **The Incident Ingestor Service:**
   - **Input:** Mock JSON stream mimicking Sentry logs (or real API if simple).
   - **Logic:** Group recurring errors by signature/release; apply thresholds + cooldown windows.
   - **Output:** Use `BacklogInterface.create_ticket` to file an investigation/fix ticket with evidence and an idempotency key.

2. **The Coverage Gap Scanner:**
   - **Input:** Repository access.
   - **Logic:** Run coverage (`pytest --cov`), identify high-churn modules below coverage floor.
   - **Output:** Ticket: `Write tests for [Module X] to raise coverage above [target]%` with acceptance criteria.

3. **The Dispatcher:**
   - Write a cron-compatible script `run_discovery.py` that executes both services every 4 hours.
   - Add duplicate suppression so the same issue does not create repeated tickets each run.

**Output:**

- Python code for `incident_ingestor.py` and `coverage_scanner.py`.
- `run_discovery.py` entry point.
