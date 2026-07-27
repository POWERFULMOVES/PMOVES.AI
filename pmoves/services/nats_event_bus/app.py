"""nats_event_bus — HTTP API.

Read endpoints are open. Write endpoints require
X-PMOVES-NatsBus-Token, which is loaded from NATS_EVENT_BUS_TOKEN at
service start. The token check is fail-closed: missing service token
disables all writes (returns 503 with a clear error pointing the
operator to set the env var). Same pattern as pinokio_bridge — the
two services use different header names so tokens can be scoped per
service.

Run with: uvicorn nats_event_bus.app:app --host 127.0.0.1 --port 8131

Port: 8131 (next to pinokio_bridge 8130).
"""
# NOTE: do NOT add `from __future__ import annotations` — Pydantic v2
# + FastAPI Body() need real class refs at runtime, not PEP 563 strings.
import logging
import os
import secrets
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

# Make the slice-3 service standalone — `pmoves/services/common` is
# two levels up from this file, but the canonical import path is
# `services.common.events`. Try both so the app works in the docker
# image (where pmoves/ is the PYTHONPATH root) and in repo-relative
# pytest runs.
try:
    from services.common.events import envelope as _envelope  # type: ignore
    from services.common.events import load_schema, validate_payload  # type: ignore
except ImportError:  # pragma: no cover — local/dev path
    _HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..")))
    from services.common.events import envelope as _envelope  # type: ignore
    from services.common.events import load_schema, validate_payload  # type: ignore

from .state import DEFAULT_TOPICS, DIRECTORY_TOPIC, EventCache, NatsSubscriber, PRESENCE_TOPIC


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

PORT = int(os.environ.get("NATS_EVENT_BUS_PORT", "8131"))
HOST = os.environ.get("NATS_EVENT_BUS_HOST", "127.0.0.1")
NATS_URL = os.environ.get("NATS_URL", "")
BUS_TOKEN = os.environ.get("NATS_EVENT_BUS_TOKEN", "")
# When true, skip the NATS subscriber at startup. Useful for tests and
# for operators who want a pure HTTP relay without consuming NATS.
DISABLE_SUBSCRIBER = os.environ.get("NATS_EVENT_BUS_DISABLE_SUBSCRIBER", "").lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("nats_event_bus")


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class PublishRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="One of the configured slice-3 topics.")
    payload: Dict[str, Any] = Field(..., description="Topic-typed payload (validated against the topic schema).")
    correlation_id: Optional[str] = Field(default=None, description="Optional correlation id propagated to the envelope.")
    parent_id: Optional[str] = Field(default=None, description="Optional parent envelope id (chain).")
    source: str = Field(default="nats_event_bus", description="Free-form source label (caller identity).")


# --------------------------------------------------------------------------
# App factory
# --------------------------------------------------------------------------

def create_app(
    cache: Optional[EventCache] = None,
    subscriber: Optional[NatsSubscriber] = None,
    token: Optional[str] = None,
) -> FastAPI:
    """Create the FastAPI app. `cache` / `subscriber` / `token` are
    injectable for tests; in production they are loaded from env."""

    app = FastAPI(
        title="nats_event_bus",
        version="0.1.0",
        description=(
            "HTTP-fronted event bus for the slice-3 creator-collab subjects "
            "(comfy.collab.{prompt,progress,artifact}.v1, room.presence.v1, "
            "room.directory.v1). Validates incoming events against the topic "
            "schema, holds a per-topic in-memory ring buffer, and optionally "
            "subscribes to NATS to fill the cache from external publishers."
        ),
    )

    if cache is None:
        cache = EventCache()
    if subscriber is None and not DISABLE_SUBSCRIBER:
        subscriber = NatsSubscriber(cache=cache, topics=cache.topics, nats_url=NATS_URL)
    if token is None:
        token = BUS_TOKEN

    app.state.cache = cache
    app.state.subscriber = subscriber
    app.state.bus_token = token

    def require_token(
        x_pmoves_nats_bus_token: Optional[str] = Header(default=None, alias="X-PMOVES-NatsBus-Token")
    ) -> None:
        """Fail-closed token check for write endpoints. If the service
        has no token configured (NATS_EVENT_BUS_TOKEN unset), all writes
        are disabled with 503. If a token IS configured, the header
        must match."""
        if not app.state.bus_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "NATS_EVENT_BUS_TOKEN not configured on the service. "
                    "Set it in the bus service environment to enable writes."
                ),
            )
        if not x_pmoves_nats_bus_token or not secrets.compare_digest(
            x_pmoves_nats_bus_token, app.state.bus_token
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-PMOVES-NatsBus-Token header",
            )

    # ----------------------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------------------

    @app.on_event("startup")
    async def _startup() -> None:
        sub = app.state.subscriber
        if sub is not None and sub.enabled:
            await sub.start()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        sub = app.state.subscriber
        if sub is not None:
            await sub.stop()

    # ----------------------------------------------------------------------
    # Health
    # ----------------------------------------------------------------------

    @app.get("/healthz")
    def healthz() -> Dict[str, Any]:
        sub = app.state.subscriber
        return {
            "status": "ok",
            "topics": app.state.cache.topics,
            "nats_connected": bool(sub and sub.connected),
            "nats_enabled": bool(sub and sub.enabled),
            "writes_enabled": bool(app.state.bus_token),
            "ts": datetime.now(timezone.utc).isoformat() + "Z",
        }

    # ----------------------------------------------------------------------
    # Topics
    # ----------------------------------------------------------------------

    @app.get("/v1/topics")
    def list_topics() -> Dict[str, Any]:
        return {"topics": app.state.cache.topics}

    # ----------------------------------------------------------------------
    # Events
    # ----------------------------------------------------------------------

    @app.get("/v1/events/{topic}")
    async def read_events(
        topic: str,
        since: Optional[str] = Query(default=None, description="ISO-8601 timestamp; only return events newer."),
        limit: int = Query(default=50, ge=1, le=200, description="Max envelopes to return (1-200)."),
    ) -> Dict[str, Any]:
        if topic not in app.state.cache.topics:
            raise HTTPException(404, f"Unknown or unregistered topic: {topic}")
        envs = await app.state.cache.recent(topic, since=since, limit=limit)
        return {"topic": topic, "count": len(envs), "events": envs}

    @app.post("/v1/publish", dependencies=[Depends(require_token)])
    async def publish(req: PublishRequest) -> Dict[str, Any]:
        """Validate the payload against the topic schema, build the
        standard envelope, append to the in-memory cache, and (best-
        effort) publish to NATS. Returns the envelope on success."""
        if req.topic not in app.state.cache.topics:
            raise HTTPException(404, f"Unknown or unregistered topic: {req.topic}")
        # Validate payload against the topic schema. Raises on failure;
        # convert to 422 with the validator error.
        try:
            validate_payload(req.topic, req.payload)
        except Exception as e:  # noqa: BLE001 — convert to HTTP
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Payload failed schema validation for {req.topic}: {e}",
            ) from e

        env = _envelope(
            req.topic,
            req.payload,
            correlation_id=req.correlation_id,
            parent_id=req.parent_id,
            source=req.source,
        )
        await app.state.cache.append(req.topic, env)

        # Best-effort NATS publish. Failures are logged, not raised.
        sub = app.state.subscriber
        if sub is not None and sub.enabled and sub.connected and sub._nc is not None:
            try:
                import json as _json
                await sub._nc.publish(req.topic, _json.dumps(env).encode())
            except Exception as e:  # noqa: BLE001
                logger.warning("nats publish failed for %s (envelope still cached): %s", req.topic, e)

        return {"envelope": env}

    # ----------------------------------------------------------------------
    # Convenience reads
    # ----------------------------------------------------------------------

    @app.get("/v1/snapshot/room-directory")
    async def latest_room_directory() -> Dict[str, Any]:
        """Return the most recent room.directory.v1 snapshot, or 404 if none seen yet."""
        env = await app.state.cache.latest(DIRECTORY_TOPIC)
        if env is None:
            raise HTTPException(404, f"No recent event for {DIRECTORY_TOPIC}")
        return {"topic": DIRECTORY_TOPIC, "envelope": env}

    @app.get("/v1/presence/{room_id}")
    async def room_presence(room_id: str, limit: int = Query(default=20, ge=1, le=200)) -> Dict[str, Any]:
        """Return the most recent N presence events for a room (any action)."""
        events = await app.state.cache.filter(
            PRESENCE_TOPIC,
            lambda e: e.get("payload", {}).get("room_id") == room_id,
        )
        return {"room_id": room_id, "count": min(len(events), limit), "events": events[-limit:]}

    return app


# Module-level app for `uvicorn nats_event_bus.app:app`.
app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
