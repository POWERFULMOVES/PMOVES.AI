"""Showtime API — aggregates health probes, NATS events, agent cards, and notebook feeds.

Port 9225. Provides REST + SSE endpoints for the Showtime dashboard.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from starlette.responses import Response

from health_probe import probe_all
from nats_sse import nats_event_generator, NATS_URL
from agent_registry import load_cards, enrich_with_health, get_card_by_id
from notebook_client import fetch_notebooks
from cgp_decoder import validate_cgp, ValidationResult
from updater import (
    SAFE_DEFAULT_BLAST_RADIUS,
    evaluate_gate,
    run_update,
)

logger = logging.getLogger("showtime")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
HEALTH_PROBE_DURATION = Histogram(
    "showtime_health_probe_duration_seconds",
    "Time spent probing all services",
)
SHOWTIME_STATE = Gauge(
    "showtime_state_ordinal",
    "Showtime state: 0=preflight, 1=hold, 2=showtime",
)
SERVICES_READY = Gauge(
    "showtime_services_ready",
    "Number of services reporting healthy",
)
SSE_CONNECTIONS = Gauge(
    "showtime_sse_connections",
    "Active SSE connections",
)
CGP_VALIDATIONS = Counter(
    "showtime_cgp_validations_total",
    "CGP validation requests",
    ["result"],
)
NATS_PUBLISH_FAILURES = Counter(
    "showtime_nats_publish_failures_total",
    "NATS publish failures for showtime state events",
)

STATE_ORDINALS = {"preflight": 0, "hold": 1, "showtime": 2}

# ---------------------------------------------------------------------------
# NATS connection (lazy, for publishing showtime state transitions)
# ---------------------------------------------------------------------------
_nats_client = None
_nats_lock = asyncio.Lock()


async def _get_nats():
    global _nats_client
    async with _nats_lock:
        if _nats_client is None or not _nats_client.is_connected:
            from nats.aio.client import Client as NATS
            nc = NATS()
            try:
                await nc.connect(NATS_URL)
                _nats_client = nc
            except Exception as exc:
                logger.warning("NATS publish connection failed: %s", exc)
                _nats_client = None
    return _nats_client


_last_state: str | None = None


async def _publish_update_event(subject: str, payload: dict[str, Any]) -> None:
    """Publish a showtime updater event to NATS (best-effort)."""
    nc = await _get_nats()
    if not nc:
        return
    try:
        await nc.publish(subject, json.dumps(payload).encode())
    except Exception as exc:
        NATS_PUBLISH_FAILURES.inc()
        logger.warning("Failed to publish %s: %s", subject, exc)


async def _run_preflight_updater() -> None:
    """On startup, if the readiness state would be preflight, attempt a gated,
    blast-radius-scoped update.

    * Checks the two-factor CHIT+OAuth gate. If locked -> publish
      ``showtime.update.blocked.v1`` and return.
    * If unlocked -> publish ``showtime.update.started.v1``, run
      ``run_update`` against the SAFE DEFAULT (data-tier) radius, then publish
      ``showtime.update.complete.v1`` with a summary.

    Opt out by setting ``SHOWTIME_UPDATER_AUTORUN=0``. Never raises — startup
    must not fail because of the updater.
    """
    if not _is_truthy(os.environ.get("SHOWTIME_UPDATER_AUTORUN", "1")):
        logger.info("Preflight updater disabled (SHOWTIME_UPDATER_AUTORUN=0)")
        return
    try:
        report = await probe_all()
        state = report.get("state")
        if state != "preflight":
            logger.info("Preflight updater skipped (state=%s, not preflight)", state)
            return

        gate = evaluate_gate()
        if not gate.get("unlocked"):
            logger.info("Preflight updater gate locked: %s", gate.get("reason"))
            await _publish_update_event(
                "showtime.update.blocked.v1",
                {"source": "showtime-api", "gate": gate, "state": state},
            )
            return

        await _publish_update_event(
            "showtime.update.started.v1",
            {"source": "showtime-api", "blast_radius": list(SAFE_DEFAULT_BLAST_RADIUS)},
        )
        summary = await asyncio.to_thread(run_update, None)
        await _publish_update_event(
            "showtime.update.complete.v1",
            {"source": "showtime-api", "summary": summary},
        )
        logger.info("Preflight updater complete: %s", summary.get("status"))
    except Exception:
        logger.exception("Preflight updater failed (non-fatal)")


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


async def _check_state_transition(new_state: str) -> None:
    """Publish NATS event on state transition to showtime."""
    global _last_state
    if _last_state != new_state:
        if new_state == "showtime":
            nc = await _get_nats()
            if nc:
                try:
                    await nc.publish(
                        "showtime.all_green.v1",
                        json.dumps({"state": "showtime", "source": "showtime-api"}).encode(),
                    )
                except Exception as exc:
                    NATS_PUBLISH_FAILURES.inc()
                    logger.warning("Failed to publish showtime event: %s", exc)
        _last_state = new_state


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Showtime API starting on port %s", os.environ.get("PORT", "9225"))
    # Fire the gated preflight updater as a background task so a slow update
    # (or a dead NATS broker) never blocks startup.
    updater_task = asyncio.create_task(_run_preflight_updater())
    yield
    if not updater_task.done():
        updater_task.cancel()
        try:
            await updater_task
        except (asyncio.CancelledError, Exception):
            pass
    # Cleanup NATS on shutdown
    global _nats_client
    if _nats_client and _nats_client.is_connected:
        await _nats_client.drain()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PMOVES Showtime API",
    version="1.0.0",
    lifespan=lifespan,
)

_cors_origins = [
    o.strip()
    for o in os.environ.get(
        "SHOWTIME_CORS_ORIGINS", "http://localhost:3000,http://localhost:9225"
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "showtime-api"}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health/all")
async def health_all():
    """Parallel probe of all PMOVES services with tier metadata."""
    with HEALTH_PROBE_DURATION.time():
        report = await probe_all()

    SERVICES_READY.set(report["ready"])
    SHOWTIME_STATE.set(STATE_ORDINALS.get(report["state"], 0))
    await _check_state_transition(report["state"])
    return report


@app.get("/updater/gate")
async def updater_gate():
    """Two-factor updater gate (non-placeholder CHIT passphrase AND Google
    session token). Fails closed.

    **Coarse by design** (Safe-Activation Contract Clause 3 — a reachable surface
    must not leak its security posture): returns only ``{"unlocked": bool}`` so a
    caller who can reach showtime-api cannot enumerate *which* factor is absent.
    The per-factor breakdown stays in-process (lifespan/CLI call ``evaluate_gate``
    directly). The CHIT escape hatch is **env-only** (``SHOWTIME_UPDATER_SKIP_CHIT``)
    and is never accepted over HTTP."""
    gate = evaluate_gate()
    return {"unlocked": bool(gate.get("unlocked", False))}


@app.get("/sse/events")
async def sse_events():
    """SSE stream from NATS subjects."""
    SSE_CONNECTIONS.inc()

    async def _stream():
        try:
            async for event in nats_event_generator():
                yield event
        except Exception:
            logger.exception("SSE stream error")
            yield 'event: error\ndata: {"error": "stream interrupted"}\n\n'
        finally:
            SSE_CONNECTIONS.dec()

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/agents")
async def agents_list():
    """Agent card registry enriched with live health."""
    cards = load_cards()
    enriched = await enrich_with_health(cards)
    return {"agents": enriched, "count": len(enriched)}


@app.get("/agents/{agent_id}")
async def agent_detail(agent_id: str):
    """Single agent card with full details and live health."""
    cards = load_cards()
    enriched = await enrich_with_health(cards)
    card = get_card_by_id(enriched, agent_id)
    if card is None:
        return Response(
            content=json.dumps({"error": f"Agent '{agent_id}' not found"}),
            status_code=404,
            media_type="application/json",
        )
    return card


@app.get("/notebook/feed")
async def notebook_feed(
    cursor: str | None = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Paginated notebooks from Open Notebook API."""
    return await fetch_notebooks(cursor=cursor, limit=limit)


@app.post("/cgp/validate")
async def cgp_validate(packet: dict[str, Any]):
    """Validate a CGP packet against the CHIT geometry schema."""
    result: ValidationResult = validate_cgp(packet)
    label = "valid" if result.valid else "invalid"
    CGP_VALIDATIONS.labels(result=label).inc()
    return asdict(result)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "9225")))
