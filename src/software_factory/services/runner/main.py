"""Runner service entrypoint."""

from __future__ import annotations

import logging
import socket

from redis import Redis

from software_factory.config import get_settings
from software_factory.core.adapters import AgentAdapter, CodexAdapter
from software_factory.core.backlog import SQLAlchemyBacklog
from software_factory.core.git import GitHubPRClient
from software_factory.core.queue import RedisQueue
from software_factory.core.sandbox import SandboxManager
from software_factory.core.supervisor import RunSupervisor
from software_factory.db.session import create_engine_from_settings, create_session_factory
from software_factory.services.execution import ExecutionRunner
from software_factory.services.runner.service import RunnerService


def build_adapter_registry(enabled_harnesses: list[str]) -> dict[str, AgentAdapter]:
    """Build adapter instances for enabled harness names."""

    available: dict[str, AgentAdapter] = {
        "codex": CodexAdapter(),
    }
    adapters: dict[str, AgentAdapter] = {}
    for name in enabled_harnesses:
        adapter = available.get(name)
        if adapter is not None:
            adapters[name] = adapter

    if not adapters:
        raise ValueError(f"No valid adapters configured for enabled_harnesses={enabled_harnesses}")
    return adapters


def build_runner_service() -> RunnerService:
    """Construct a fully wired runner service."""

    settings = get_settings()
    engine = create_engine_from_settings()
    session_factory = create_session_factory(engine)

    backlog = SQLAlchemyBacklog(
        session_factory=session_factory,
        lease_ttl_seconds=settings.default_lease_ttl_seconds,
    )
    supervisor = RunSupervisor(
        backlog=backlog,
        session_factory=session_factory,
        heartbeat_timeout_seconds=settings.run_heartbeat_timeout_seconds,
    )
    sandbox_manager = SandboxManager(
        workspace_root=settings.sandbox_workspace_root,
        use_local_mode=settings.environment == "local",
    )
    adapters = build_adapter_registry(settings.enabled_harnesses)
    pr_client = GitHubPRClient(
        token=settings.github_token,
        dry_run=settings.environment == "local" or settings.github_token is None,
    )
    execution_runner = ExecutionRunner(
        backlog=backlog,
        supervisor=supervisor,
        sandbox_manager=sandbox_manager,
        adapters=adapters,
        pr_client=pr_client,
        session_factory=session_factory,
        artifacts_root=settings.artifacts_root,
    )

    redis_client = Redis.from_url(settings.redis_url)
    queue = RedisQueue(
        redis_client=redis_client,
        name=settings.queue_name,
        dlq_name=settings.dead_letter_queue_name,
    )
    owner = f"runner-{socket.gethostname()}"

    return RunnerService(
        queue=queue,
        execution_runner=execution_runner,
        session_factory=session_factory,
        adapters=adapters,
        owner=owner,
        poll_interval_seconds=settings.runner_poll_interval_seconds,
        default_base_branch=settings.default_base_branch,
        push_branches=settings.push_branches,
    )


def main() -> None:
    """Run queue-driven worker loop."""

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    service = build_runner_service()
    service.run_forever()


if __name__ == "__main__":
    main()
