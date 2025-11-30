from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

import httpx
from fastapi import FastAPI, HTTPException, Query, Response
from nats.aio.client import Client as NATS
from nats.aio.msg import Msg
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="PMOVES-SUPASERCH", version="0.1.0")


# Prometheus metrics -------------------------------------------------------
REQUEST_COUNTER = Counter(
    "supaserch_requests_total",
    "Total SupaSerch requests processed",
    labelnames=("channel",),
)
REQUEST_ERRORS = Counter(
    "supaserch_request_errors_total",
    "Total SupaSerch request errors",
    labelnames=("channel", "reason"),
)
REQUEST_LATENCY = Histogram(
    "supaserch_request_latency_seconds",
    "Latency of SupaSerch aggregation pipeline",
    labelnames=("channel",),
)
FALLBACK_COUNTER = Counter(
    "supaserch_http_fallback_total",
    "HTTP fallback invocations grouped by status",
    labelnames=("status",),
)
FALLBACK_LATENCY = Histogram(
    "supaserch_http_fallback_latency_seconds",
    "Latency of HTTP fallback invocations",
    labelnames=("status",),
)
NATS_CONNECTION_GAUGE = Gauge(
    "supaserch_nats_connected",
    "NATS connection status (1=connected, 0=disconnected)",
)


@dataclass
class SupaSerchContext:
    request_id: str
    channel: str
    correlation_id: Optional[str]


def _default_fallback_url() -> str:
    """Return the default fallback endpoint."""

    port = os.getenv("SUPASERCH_PORT", "8099")
    return os.getenv("SUPASERCH_HTTP_FALLBACK_URL", f"http://127.0.0.1:{port}/healthz")


async def run_http_fallback(query: str, *, request_id: str) -> Dict[str, Any]:
    """Invoke the HTTP fallback, returning diagnostics for observability."""

    fallback_url_template = _default_fallback_url().strip()
    if not fallback_url_template:
        FALLBACK_COUNTER.labels(status="stub").inc()
        FALLBACK_LATENCY.labels(status="stub").observe(0.0)
        return {
            "status": "ok",
            "url": None,
            "via": "stub",
            "request_id": request_id,
            "latency_ms": 0.0,
            "payload": {
                "message": "No HTTP fallback configured; returning static guidance.",
                "suggestions": [
                    "Set SUPASERCH_HTTP_FALLBACK_URL to a search API endpoint",
                    "Or rely on the default /healthz probe for availability checks",
                ],
            },
        }
    include_query_param = False
    if "{encoded_query}" in fallback_url_template:
        target_url = fallback_url_template.replace("{encoded_query}", quote_plus(query))
    elif "{query}" in fallback_url_template:
        target_url = fallback_url_template.replace("{query}", query)
    else:
        target_url = fallback_url_template
        include_query_param = True

    status_label = "error"
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=float(os.getenv("SUPASERCH_FALLBACK_TIMEOUT", "6.0"))) as client:
            response = await client.get(target_url, params={"q": query} if include_query_param else None)
        latency = time.perf_counter() - start
        payload: Any
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = response.text[:2048]
        status_label = "ok" if response.is_success else "http_error"
        return {
            "status": "ok" if response.is_success else "error",
            "status_code": response.status_code,
            "url": target_url,
            "via": "http",
            "latency_ms": round(latency * 1000, 2),
            "payload": payload,
            "request_id": request_id,
        }
    except Exception as exc:  # noqa: BLE001
        latency = time.perf_counter() - start
        logger.warning("HTTP fallback failed: %s", exc)
        return {
            "status": "error",
            "url": target_url,
            "via": "http",
            "error": str(exc),
            "latency_ms": round(latency * 1000, 2),
            "request_id": request_id,
        }
    finally:
        FALLBACK_COUNTER.labels(status=status_label).inc()
        FALLBACK_LATENCY.labels(status=status_label).observe(latency)


def _stub_multimodal_plan(query: str) -> list[Dict[str, Any]]:
    """Return the staged plan describing the multimodal aggregation pipeline."""

    return [
        {
            "stage": "seed_intent",
            "summary": "Capture user intent and metadata from the SupaSerch request envelope.",
            "status": "complete",
            "artifacts": {"query": query},
        },
        {
            "stage": "deepresearch",
            "summary": "Coordinate DeepResearch worker runs (OpenRouter/local models) for broad retrieval.",
            "status": "pending",
        },
        {
            "stage": "archon_agent_zero",
            "summary": "Invoke Archon/Agent Zero MCP tools for repo analysis, summarisation, and enrichment.",
            "status": "pending",
        },
        {
            "stage": "geometry_cgp",
            "summary": "Emit CGP packets onto the Geometry Bus and Supabase tables for downstream consumers.",
            "status": "pending",
        },
        {
            "stage": "http_fallback",
            "summary": "Sustain availability by querying the configured HTTP search fallback.",
            "status": "pending",
        },
    ]


async def run_pipeline(query: str, context: SupaSerchContext, *, envelope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute the multimodal aggregation pipeline."""

    plan = _stub_multimodal_plan(query)
    fallback = await run_http_fallback(query, request_id=context.request_id)
    plan[-1]["status"] = "complete" if fallback.get("status") == "ok" else "error"

    return {
        "request_id": context.request_id,
        "query": query,
        "channel": context.channel,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": context.correlation_id,
        "plan": plan,
        "fallback": fallback,
        "envelope": envelope or {},
    }


async def process_request(query: str, *, context: SupaSerchContext, envelope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Common entrypoint used by HTTP and NATS pipelines."""

    if not query:
        raise ValueError("query is required")
    return await run_pipeline(query, context, envelope=envelope)


async def _handle_nats_message(msg: Msg) -> None:
    REQUEST_COUNTER.labels(channel="nats").inc()
    start = time.perf_counter()
    try:
        data = json.loads(msg.data.decode("utf-8"))
        query = data.get("query") or data.get("payload", {}).get("query")
        request_id = data.get("request_id") or uuid.uuid4().hex
        correlation_id = data.get("correlation_id") or data.get("payload", {}).get("correlation_id")
        context = SupaSerchContext(request_id=request_id, channel="nats", correlation_id=correlation_id)
        result = await process_request(query, context=context, envelope=data)
        nc: Optional[NATS] = getattr(app.state, "nats", None)
        if nc is not None and nc.is_connected:
            await nc.publish("supaserch.result.v1", json.dumps(result).encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        REQUEST_ERRORS.labels(channel="nats", reason=exc.__class__.__name__).inc()
        logger.exception("Error handling NATS SupaSerch request")
    finally:
        REQUEST_LATENCY.labels(channel="nats").observe(time.perf_counter() - start)


async def _connect_nats() -> None:
    url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = NATS()
    try:
        await nc.connect(url)
        app.state.nats = nc
        await nc.subscribe("supaserch.request.v1", cb=_handle_nats_message)
        NATS_CONNECTION_GAUGE.set(1)
        logger.info("Connected to NATS at %s", url)
    except Exception as exc:  # noqa: BLE001
        NATS_CONNECTION_GAUGE.set(0)
        logger.warning("Failed to connect to NATS at %s: %s", url, exc)


@app.on_event("startup")
async def on_startup() -> None:
    app.state.nats = None
    asyncio.create_task(_connect_nats())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    nc: Optional[NATS] = getattr(app.state, "nats", None)
    if nc is not None and not nc.is_closed:
        try:
            await nc.drain()
        finally:
            NATS_CONNECTION_GAUGE.set(0)


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    nc: Optional[NATS] = getattr(app.state, "nats", None)
    return {
        "status": "ok",
        "service": "pmoves-supaserch",
        "nats": bool(nc and nc.is_connected),
        "http_fallback": _default_fallback_url(),
    }


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/v1/search")
async def search(q: str = Query(..., min_length=1, description="Search query")) -> Dict[str, Any]:
    channel = "http"
    REQUEST_COUNTER.labels(channel=channel).inc()
    start = time.perf_counter()
    context = SupaSerchContext(request_id=uuid.uuid4().hex, channel=channel, correlation_id=None)
    try:
        result = await process_request(q, context=context, envelope={"query": q, "channel": channel})
        return result
    except ValueError as exc:
        REQUEST_ERRORS.labels(channel=channel, reason="ValueError").inc()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        REQUEST_ERRORS.labels(channel=channel, reason=exc.__class__.__name__).inc()
        logger.exception("HTTP search failed")
        raise HTTPException(status_code=500, detail="pipeline_error") from exc
    finally:
        REQUEST_LATENCY.labels(channel=channel).observe(time.perf_counter() - start)

