"""Health probing module.

Reuses ENDPOINTS from flight_check_retro.py and adds tier/type metadata
for the Showtime dashboard. Probes all services in parallel via httpx.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from typing import Any

import httpx

PROBE_TIMEOUT = float(os.environ.get("SHOWTIME_PROBE_TIMEOUT", "3.0"))

# Canonical service list with tier metadata.
# Mirrors flight_check_retro.py ENDPOINTS with additional classification.
# NOTE: this is a hand-kept copy, not an import; keep the two in step
# (pmoves/tests/tools/test_archon_probe_surface.py pins the Archon rows of both).
SERVICE_CATALOG: list[dict[str, Any]] = [
    {"name": "Supabase REST", "url": f"http://127.0.0.1:{os.environ.get('SUPABASE_REST_PORT', '65421')}/rest/v1", "tier": 1, "type": "Data"},
    {"name": "Hi-RAG v2 CPU", "url": f"http://localhost:{os.environ.get('HIRAG_V2_HOST_PORT', '8086')}/", "tier": 4, "type": "Worker"},
    {"name": "Hi-RAG v2 GPU", "url": f"http://localhost:{os.environ.get('HIRAG_V2_GPU_HOST_PORT', '8087')}/", "tier": 4, "type": "Worker"},
    {"name": "Presign", "url": "http://localhost:8088/healthz", "tier": 2, "type": "API"},
    # Archon 0.6.0+: /api/health is the only health route; the SPA catch-all answers
    # any other path 200 HTML, so the body must be JSON (expect_json). UI on host 3737.
    {"name": "Archon API", "url": "http://localhost:8091/api/health", "tier": 6, "type": "Agent", "expect_json": True},
    {"name": "Archon UI", "url": "http://localhost:3737", "tier": 7, "type": "UI", "expect_title": "Archon"},
    {"name": "Agent Zero API", "url": "http://localhost:8080/healthz", "tier": 6, "type": "Agent"},
    {"name": "PMOVES.YT", "url": "http://localhost:8077/", "tier": 5, "type": "Media"},
    {"name": "Grafana", "url": f"http://localhost:{os.environ.get('GRAFANA_PORT', '3002')}", "tier": 7, "type": "UI"},
    {"name": "Loki", "url": "http://localhost:3100/ready", "tier": 1, "type": "Data"},
    {"name": "Channel Monitor", "url": "http://localhost:8097/healthz", "tier": 4, "type": "Worker"},
    {"name": "TensorZero UI", "url": "http://localhost:4000", "tier": 7, "type": "UI"},
    {"name": "TensorZero GW", "url": f"http://localhost:{os.environ.get('TENSORZERO_PORT', '3030')}", "tier": 2, "type": "API"},
    {"name": "Open Notebook", "url": "http://localhost:8503", "tier": 1, "type": "Data"},
    {"name": "Cipher Memory", "url": "http://localhost:8105/health", "tier": 1, "type": "Data"},
    {"name": "BoTZ Gateway", "url": "http://localhost:8054/healthz", "tier": 6, "type": "Agent"},
    {"name": "DeepResearch", "url": "http://localhost:8098/healthz", "tier": 3, "type": "LLM"},
    {"name": "Flute-Gateway", "url": "http://localhost:8055/healthz", "tier": 2, "type": "API"},
    {"name": "SupaSerch", "url": "http://localhost:8099/healthz", "tier": 6, "type": "Agent"},
    {"name": "n8n UI", "url": "http://localhost:5678", "tier": 4, "type": "Worker"},
    {"name": "Supabase Studio", "url": "http://127.0.0.1:65433", "tier": 7, "type": "UI"},
]

TIER_COLORS = {
    1: "#92400E",   # Data  - Brown
    2: "#3B82F6",   # API   - Blue
    3: "#EF4444",   # LLM   - Red
    4: "#EAB308",   # Worker - Yellow
    5: "#06B6D4",   # Media - Cyan
    6: "#A855F7",   # Agent - Purple
    7: "#F5F5F5",   # UI    - White
}


@dataclass
class ProbeResult:
    name: str
    url: str
    ok: bool
    status_code: int
    latency_ms: float
    tier: int
    type: str
    tier_color: str
    error: str = ""


logger = logging.getLogger("showtime.health_probe")


def _json_health_ok(content_type: str, body: str) -> bool:
    """True only for a JSON body reporting {"ok": true} or {"status": "ok"}."""
    if "json" not in (content_type or "").lower():
        return False
    try:
        payload = json.loads(body)
    except ValueError:
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("ok") is True:
        return True
    return str(payload.get("status", "")).lower() == "ok"


def _html_title_ok(content_type: str, body: str, title: str) -> bool:
    """True only for an HTML page whose <title> is exactly `title`."""
    if "html" not in (content_type or "").lower():
        return False
    return f"<title>{title}</title>" in (body or "")


async def _probe_one(client: httpx.AsyncClient, svc: dict[str, Any]) -> ProbeResult:
    t0 = time.monotonic()
    error = ""
    try:
        resp = await client.get(svc["url"], timeout=PROBE_TIMEOUT)
        ok = 200 <= resp.status_code < 400
        code = resp.status_code
        if ok and svc.get("expect_json"):
            ok = _json_health_ok(resp.headers.get("content-type", ""), resp.text)
            if not ok:
                error = "expected a JSON health body reporting ok"
        if ok and svc.get("expect_title"):
            ok = _html_title_ok(resp.headers.get("content-type", ""), resp.text, svc["expect_title"])
            if not ok:
                error = f"expected an HTML page titled {svc['expect_title']!r}"
    except (httpx.ConnectError, httpx.ConnectTimeout):
        ok = False
        code = 0
    except Exception as exc:
        ok = False
        code = 0
        error = type(exc).__name__
        logger.debug("Probe failed for %s: %s", svc["name"], exc)
    latency = round((time.monotonic() - t0) * 1000, 1)
    return ProbeResult(
        name=svc["name"],
        url=svc["url"],
        ok=ok,
        status_code=code,
        latency_ms=latency,
        tier=svc["tier"],
        type=svc["type"],
        tier_color=TIER_COLORS.get(svc["tier"], "#666666"),
        error=error,
    )


async def probe_all() -> dict[str, Any]:
    """Probe all services in parallel. Returns aggregated health report."""
    async with httpx.AsyncClient() as client:
        tasks = [_probe_one(client, svc) for svc in SERVICE_CATALOG]
        results = await asyncio.gather(*tasks)

    results_sorted = sorted(results, key=lambda r: (r.tier, r.name))
    ready = sum(1 for r in results_sorted if r.ok)
    total = len(results_sorted)
    pct = round(ready / total * 100) if total else 0

    if pct == 100:
        state = "showtime"
    elif pct >= 80:
        state = "hold"
    else:
        state = "preflight"

    return {
        "ready": ready,
        "total": total,
        "percent": pct,
        "state": state,
        "all_green": ready == total,
        "services": [asdict(r) for r in results_sorted],
    }
