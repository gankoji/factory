"""Dispatcher process entrypoint."""

from __future__ import annotations

import logging

from redis import Redis

from software_factory.config import get_settings
from software_factory.core.backlog import SQLAlchemyBacklog
from software_factory.core.queue import RedisQueue
from software_factory.db.session import create_engine_from_settings, create_session_factory
from software_factory.services.manager.control_state import RedisControlState
from software_factory.services.manager.dispatcher import DispatcherService


def build_dispatcher_service() -> DispatcherService:
    """Construct manager-side dispatcher service."""

    settings = get_settings()
    engine = create_engine_from_settings()
    session_factory = create_session_factory(engine)

    backlog = SQLAlchemyBacklog(
        session_factory=session_factory,
        lease_ttl_seconds=settings.default_lease_ttl_seconds,
    )

    redis_client = Redis.from_url(settings.redis_url)
    queue = RedisQueue(
        redis_client=redis_client,
        name=settings.queue_name,
        dlq_name=settings.dead_letter_queue_name,
    )
    control_state = RedisControlState(redis_client)

    return DispatcherService(
        backlog=backlog,
        queue=queue,
        control_state=control_state,
        poll_interval_seconds=settings.manager_dispatch_poll_interval_seconds,
        batch_size=settings.manager_dispatch_batch_size,
    )


def main() -> None:
    """Run manager dispatch loop forever."""

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    service = build_dispatcher_service()
    service.run_forever()


if __name__ == "__main__":
    main()
