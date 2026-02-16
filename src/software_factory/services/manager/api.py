"""Control-plane manager API."""

from __future__ import annotations

from fastapi import FastAPI
from redis import Redis
from sqlalchemy import text

from software_factory.config import get_settings
from software_factory.db.session import create_engine_from_settings

app = FastAPI(title="Software Factory Manager", version="0.1.0")

_engine = create_engine_from_settings()
_redis = Redis.from_url(get_settings().redis_url)
_control_state = {"paused": False}


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe endpoint."""

    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Readiness probe endpoint."""

    with _engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    _redis.ping()
    return {"status": "ready"}


@app.get("/control/status")
def control_status() -> dict[str, bool]:
    """Return current control-plane pause status."""

    return {"paused": _control_state["paused"]}


@app.post("/control/pause")
def pause() -> dict[str, bool]:
    """Pause new dispatches."""

    _control_state["paused"] = True
    return {"paused": True}


@app.post("/control/resume")
def resume() -> dict[str, bool]:
    """Resume new dispatches."""

    _control_state["paused"] = False
    return {"paused": False}
