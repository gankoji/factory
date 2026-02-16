# Role: Principal Platform Engineer

# Objective: Scaffold a Harness-First Control Plane

We are building a 24/7 autonomous delivery system that **orchestrates existing agent harnesses** instead of creating custom agents.

## The Stack

- **Language:** Python 3.11+
- **Orchestration:** Lightweight supervisor + queue/leases (no custom LangGraph cognition required)
- **Containerization:** Docker (ephemeral run sandboxes)
- **Harnesses:** Codex CLI, Claude Code, Gemini CLI, OpenHands (via adapters)
- **VCS:** Git / GitHub
- **Ticketing:** Linear API (or generic interface for Jira/GitHub Issues)

## Task

Please generate the initial directory structure and core shared Python libraries.

1. **Folder Structure:** Create a structure that separates `core/backlog`, `core/adapters`, `core/supervisor`, `core/sandbox`, `services/discovery`, `services/governance`, and `infrastructure/docker`.
2. **Core Libraries (`/core`):**
   - Write a `BacklogInterface` abstract base class (methods: `fetch_ready`, `claim_ticket`, `heartbeat`, `complete_ticket`, `fail_ticket`, `create_ticket`).
   - Write an `AgentAdapter` abstract base class (methods: `supports`, `launch_task`, `stream_events`, `send_control`, `collect_artifacts`, `terminate`).
   - Write a `RunSupervisor` class (methods: `dispatch`, `monitor_run`, `enforce_limits`, `recover_stale_runs`).
3. **Configuration:** Create a robust `config.py` using `pydantic` settings for API keys (ticketing, GitHub, LLM if needed), enabled harnesses, and per-harness resource limits.

**Output:**

- The bash commands to create the directories.
- The Python code for the `core` modules above.
- A `requirements.txt` file.
