# Role: Senior DevOps Architect

# Objective: Scaffold a "Tri-Loop" Autonomous Development System

I am building a 24/7 autonomous software development system with three main loops:

1. **Discovery:** Agents that analyze logs/metrics to create tickets.
2. **Execution:** Agents that pick up tickets and write code in isolated environments.
3. **Governance:** Agents that review PRs and perform maintenance.

## The Stack

- **Language:** Python 3.11+
- **Orchestration:** LangGraph (for stateful multi-agent flows)
- **Containerization:** Docker (for ephemeral agent sandboxes)
- **VCS:** Git / GitHub
- **Ticketing:** Linear API (or generic Interface for Jira/GitHub Issues)

## Task

Please generate the initial directory structure and the core shared Python libraries for this system.

1. **Folder Structure:** Create a structure that separates `core/`, `agents/discovery`, `agents/execution`, `agents/governance`, and `infrastructure/docker`.
2. **Core Library (`/core`):** - Write a `TicketInterface` abstract base class (methods: `fetch_backlog`, `create_ticket`, `update_status`).
   - Write a `GitInterface` class (methods: `clone`, `checkout_branch`, `commit`, `push_pr`).
   - Write a `LLMProvider` wrapper (compatible with OpenAI/Anthropic APIs) to standardise calls across agents.
3. **Configuration:** Create a robust `config.py` using `pydantic` settings to manage API keys (Linear, GitHub, LLM) and environment variables.

**Output:**

- The bash commands to create the directories.
- The Python code for the `core` modules mentioned above.
- A `requirements.txt` file.
