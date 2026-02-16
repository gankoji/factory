# Role: System Administrator

# Objective: Create the Main Loop and Deployment Config

We have all the components (Discovery, Execution, Governance). Now we need the main event loop to keep this running 24/7.

## Task

1. **The Main Loop (`main.py`):**
   - Write a master script that runs effectively as a daemon.
   - **Pseudo-code Logic:**
     ```python
     while True:
        # 1. Discovery Phase (Every 4 hours)
        if time_to_discover:
            run_discovery_agents()

        # 2. Execution Phase (Continuous)
        backlog = ticket_system.fetch_ready_tickets()
        if backlog and active_workers < MAX_PARALLEL_WORKERS:
            ticket = backlog.pop()
            worker = WorkerAgent(ticket)
            thread_pool.submit(worker.run)

        # 3. Governance Phase (Event Driven)
        check_for_open_prs_to_review()

        sleep(60)
     ```

2. **Docker Compose:**
   - Create a `docker-compose.yml` to run this _entire_ orchestration system itself in a container (The "Manager" container).
   - Ensure the "Manager" container has access to the Docker socket (`/var/run/docker.sock`) so it can spawn sibling containers for the Workers (Docker-in-Docker or Sibling Docker).

**Output:**

- The `main.py` orchestration script.
- The `docker-compose.yml` for the management layer.
