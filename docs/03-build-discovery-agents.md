# Role: Observability Engineer

# Objective: Create "Discovery Agents" to populate the backlog

We need to ensure our worker agents have a backlog deep enough to run 24/7. We will build two agents to generate work.

## Task

Write the code for two specific discovery agents in `agents/discovery/`.

1. **The "Sentry/Log Miner" Agent:**
   - **Input:** Accepts a mock JSON stream mimicking Sentry error logs (or a real API connection if simple).
   - **Logic:** Groups similar errors. If an error appears >10 times/hour, it triggers a "Investigation" task.
   - **Output:** Uses `TicketInterface.create_ticket` to file a bug report with the stack trace attached.

2. **The "Coverage Gap" Agent:**
   - **Input:** Access to a repository.
   - **Logic:** Runs a coverage report (e.g., `pytest --cov`). Identifies the file with the lowest test coverage.
   - **Output:** specific task: "Write unit tests for [Module X] to increase coverage above 50%."

3. **The Dispatcher:**
   - Write a simple cron-compatible script `run_discovery.py` that spins up these agents once every 4 hours.

**Output:**

- Python code for the Log Miner and Coverage Gap agents.
- The `run_discovery.py` entry point.
