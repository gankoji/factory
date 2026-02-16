# Role: System Administrator

# Objective: Build the Main Supervisor Loop and Deployment Config

We have discovery, execution, and governance services. Now we need a resilient control plane to keep multiple harness sessions running.

## Task

1. **The Main Supervisor (`main.py`):**
   - Write a master loop/service that runs continuously.
   - **Pseudo-code Logic:**
     ```python
     while True:
         run_discovery_if_due()
         recover_stale_leases()

         ready = backlog.fetch_ready()
         free_slots = supervisor.available_capacity()
         for ticket in select_dispatch_batch(ready, free_slots):
             supervisor.dispatch(ticket)

         supervisor.monitor_active_runs()
         governance.process_pending_pr_events()

         publish_metrics()
         sleep(15)
     ```
   - Include idempotency, heartbeat expiry, retry/backoff, and dead-letter handling.

2. **Docker Compose:**
   - Create a `docker-compose.yml` for the control plane services:
     - `manager` (scheduler/dispatcher API)
     - `runner` (sandbox execution worker)
     - `redis` (queue/lease cache)
     - `postgres` (tickets/runs/audit ledger)
   - Prefer isolating runtime privileges in `runner`; avoid giving broad host Docker control to `manager`.

**Output:**

- `main.py` supervisor script.
- `docker-compose.yml` for the management layer.
