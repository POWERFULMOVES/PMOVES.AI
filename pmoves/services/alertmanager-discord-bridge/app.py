# =============================================================================
# PMOVES.AI — Alertmanager Discord Bridge
# =============================================================================
# Purpose: Receives Alertmanager webhook payloads and forwards them to Discord
#          as rich embed messages with severity-based color coding.
#
# Endpoints:
#   POST /alerts              — default receiver
#   POST /alerts/critical     — critical severity
#   POST /alerts/warning      — warning severity
#   POST /alerts/info         — info severity
#   GET  /health              — health check
#   GET  /metrics             — Prometheus metrics
#
# Environment:
#   DISCORD_WEBHOOK_URL       — Discord channel webhook URL (required)
#   ALERTMANAGER_DISCORD_WEBHOOK_URL — alias for the above
#   BRIDGE_PORT               — HTTP listen port (default: 9094)
# =============================================================================
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Gauge, generate_latest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DISCORD_WEBHOOK_URL = os.getenv(
    "ALERTMANAGER_DISCORD_WEBHOOK_URL",
    os.getenv("DISCORD_WEBHOOK_URL", ""),
)
BRIDGE_PORT = int(os.getenv("BRIDGE_PORT", "9094"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ---------------------------------------------------------------------------
# Severity color map (Discord decimal color values)
# ---------------------------------------------------------------------------
SEVERITY_COLORS: dict[str, int] = {
    "critical": 0xFF0000,  # Red
    "warning": 0xFFCC00,   # Yellow/Gold
    "info": 0x3498DB,      # Blue
}
RESOLVED_COLOR = 0x2ECC71  # Green

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
alerts_received = Counter(
    "alertmanager_bridge_alerts_received_total",
    "Total alerts received from Alertmanager",
    ["severity", "status"],
)
alerts_sent = Counter(
    "alertmanager_bridge_alerts_sent_total",
    "Total alerts successfully sent to Discord",
    ["severity"],
)
alerts_failed = Counter(
    "alertmanager_bridge_alerts_failed_total",
    "Total alerts that failed to send to Discord",
    ["severity"],
)
bridge_up = Gauge(
    "alertmanager_bridge_up",
    "Bridge service is running (1=up)",
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("alertmanager-discord-bridge")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PMOVES Alertmanager Discord Bridge",
    version="1.0.0",
)
bridge_up.set(1)
START_TIME = time.time()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_severity(alert: dict[str, Any]) -> str:
    """Extract severity from an alert labels."""
    labels = alert.get("labels", {})
    return labels.get("severity", "unknown")


def _build_embed(alert: dict[str, Any]) -> dict[str, Any]:
    """Build a Discord embed from a single Alertmanager alert."""
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    status = alert.get("status", "firing")
    severity = _get_severity(alert)

    # Color
    color = RESOLVED_COLOR if status == "resolved" else SEVERITY_COLORS.get(severity, 0x95A5A6)

    # Title
    alert_name = labels.get("alertname", "Unknown Alert")
    title_prefix = "\u2705 RESOLVED" if status == "resolved" else "\U0001F6A8 FIRING"
    title = f"{title_prefix}: {alert_name}"

    # Fields
    fields: list[dict[str, str]] = []
    if severity != "unknown":
        fields.append({"name": "Severity", "value": f"**{severity.upper()}**", "inline": True})
    if "service" in labels:
        fields.append({"name": "Service", "value": labels["service"], "inline": True})
    if "job" in labels:
        fields.append({"name": "Job", "value": labels["job"], "inline": True})

    summary = annotations.get("summary", "")
    description = annotations.get("description", "")
    if summary:
        fields.append({"name": "Summary", "value": summary, "inline": False})
    if description and description != summary:
        fields.append({"name": "Description", "value": description[:1024], "inline": False})

    # Runbook link
    runbook = annotations.get("runbook_url", "")
    if runbook:
        fields.append({"name": "Runbook", "value": f"[View runbook]({runbook})", "inline": False})

    # Footer with timestamp
    starts_at = alert.get("startsAt", "")
    footer_text = f"PMOVES Alertmanager | {severity}"
    if starts_at:
        try:
            dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
            footer_text += f" | Started: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        except (ValueError, TypeError):
            pass

    embed: dict[str, Any] = {
        "title": title,
        "color": color,
        "fields": fields,
        "footer": {"text": footer_text},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return embed


async def _send_to_discord(embeds: list[dict[str, Any]]) -> bool:
    """Send embeds to Discord via webhook. Returns True on success."""
    if not DISCORD_WEBHOOK_URL:
        logger.warning("No DISCORD_WEBHOOK_URL configured - logging only")
        for embed in embeds:
            logger.info("Discord embed (not sent): %s", embed.get("title"))
        return False

    payload: dict[str, Any] = {"embeds": embeds}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(DISCORD_WEBHOOK_URL, json=payload)
            if resp.status_code in (200, 204):
                logger.info("Sent %d embed(s) to Discord", len(embeds))
                return True
            else:
                logger.error(
                    "Discord webhook failed: status=%d body=%s",
                    resp.status_code,
                    resp.text[:200],
                )
                return False
        except httpx.HTTPError as exc:
            logger.error("Discord webhook error: %s", exc)
            return False


async def _handle_alertmanager_payload(payload: dict[str, Any]) -> dict[str, int]:
    """Process an Alertmanager webhook payload. Returns counts {sent, failed}."""
    status = payload.get("status", "firing")
    alerts = payload.get("alerts", [])
    counts: dict[str, int] = {"sent": 0, "failed": 0}

    if not alerts:
        logger.info("Received payload with no alerts")
        return counts

    embeds: list[dict[str, Any]] = []
    for alert in alerts:
        severity = _get_severity(alert)
        alerts_received.labels(severity=severity, status=status).inc()
        embeds.append(_build_embed(alert))

    # Discord allows max 10 embeds per message
    batch_size = 10
    for i in range(0, len(embeds), batch_size):
        batch = embeds[i : i + batch_size]
        batch_severities = [
            _get_severity(alerts[j])
            for j in range(i, min(i + batch_size, len(alerts)))
        ]
        success = await _send_to_discord(batch)
        if success:
            for sev in batch_severities:
                alerts_sent.labels(severity=sev).inc()
            counts["sent"] += len(batch)
        else:
            for sev in batch_severities:
                alerts_failed.labels(severity=sev).inc()
            counts["failed"] += len(batch)

    return counts


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/alerts")
async def alerts_default(request: Request) -> dict[str, Any]:
    """Default alert receiver."""
    payload = await request.json()
    logger.info("Received default alerts (status=%s)", payload.get("status"))
    counts = await _handle_alertmanager_payload(payload)
    return {"status": "ok", "sent": counts["sent"], "failed": counts["failed"]}


@app.post("/alerts/critical")
async def alerts_critical(request: Request) -> dict[str, Any]:
    """Critical severity alert receiver."""
    payload = await request.json()
    logger.info("Received critical alerts (status=%s)", payload.get("status"))
    counts = await _handle_alertmanager_payload(payload)
    return {"status": "ok", "sent": counts["sent"], "failed": counts["failed"]}


@app.post("/alerts/warning")
async def alerts_warning(request: Request) -> dict[str, Any]:
    """Warning severity alert receiver."""
    payload = await request.json()
    logger.info("Received warning alerts (status=%s)", payload.get("status"))
    counts = await _handle_alertmanager_payload(payload)
    return {"status": "ok", "sent": counts["sent"], "failed": counts["failed"]}


@app.post("/alerts/info")
async def alerts_info(request: Request) -> dict[str, Any]:
    """Info severity alert receiver."""
    payload = await request.json()
    logger.info("Received info alerts (status=%s)", payload.get("status"))
    counts = await _handle_alertmanager_payload(payload)
    return {"status": "ok", "sent": counts["sent"], "failed": counts["failed"]}


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check endpoint."""
    webhook_configured = bool(DISCORD_WEBHOOK_URL)
    return {
        "status": "healthy",
        "webhook_configured": webhook_configured,
        "uptime_seconds": int(time.time() - START_TIME),
    }


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=BRIDGE_PORT)
