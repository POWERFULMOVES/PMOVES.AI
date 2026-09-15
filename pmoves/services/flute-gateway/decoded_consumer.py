#!/usr/bin/env python3
# Runtime: Run as a standalone sidecar container or systemd service alongside flute-gateway.
"""Geometry Decoded Consumer — subscribes to geometry.packet.decoded.v1.

Consumes decoded CGP packets published by cgp_consumer.py, validates packet
structure, and logs geometry data summaries for observability. Future versions
will route data to downstream integrations (cymatic visualizer, persona broadcast).

This closes the lane-3 gap: cgp_consumer publishes decoded packets to
geometry.packet.decoded.v1, but nothing consumed that subject.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from typing import Any, Dict
from urllib.parse import urlparse, urlunparse

from nats.aio.client import Client as NATS

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def _load_secret(key: str, default: str = "") -> str:
    """Read secret from env or *_FILE mount (Docker secret convention)."""
    val = os.environ.get(key)
    if val:
        return val
    file_path = os.environ.get(f"{key}_FILE")
    if file_path and os.path.exists(file_path):
        with open(file_path, encoding="utf-8") as fh:
            return fh.read().strip()
    return default


def _resolve_nats_url() -> str:
    """Resolve NATS connection URL from env vars with component fallback."""
    url = _load_secret("NATS_URL")
    if url:
        return url
    host = os.environ.get("NATS_HOST", "nats")
    port = os.environ.get("NATS_PORT", "4222")
    user = os.environ.get("NATS_USER", "")
    password = os.environ.get("NATS_PASSWORD", "")
    if user and password:
        return f"nats://{user}:{password}@{host}:{port}"
    return f"nats://{host}:{port}"


def _redact_url(url: str) -> str:
    """Strip credentials from URL for safe logging."""
    try:
        parsed = urlparse(url)
        # Redact all user-info, not just user:password — token-only URLs
        # (nats://TOKEN@host) put the secret in `username` with no password.
        if parsed.username or parsed.password:
            host = parsed.hostname or ""
            if parsed.port:
                host = f"{host}:{parsed.port}"
            return urlunparse(parsed._replace(netloc=f"***@{host}"))
    except Exception:
        pass
    return url


def _validate_decoded_packet(payload: Dict[str, Any]) -> bool:
    """Validate structure of a decoded CGP packet."""
    required = ["source_spec", "super_nodes", "control_plane"]
    return all(key in payload for key in required)


async def main():
    nc = NATS()
    nats_url = _resolve_nats_url()

    try:
        await nc.connect(nats_url, connect_timeout=10)
        logger.info("Connected to NATS (broker details withheld)")
    except Exception as e:
        # Fail fast with a non-zero exit so container supervisors (Docker/K8s)
        # restart the worker on a startup-order race instead of seeing exit 0.
        logger.error("Failed to connect to NATS: %s", type(e).__name__)
        sys.exit(1)

    subscribe_subject = os.environ.get("FLUTE_DECODED_SUBJECT", "geometry.packet.decoded.v1")
    processed = 0
    errors = 0

    async def message_handler(msg):
        nonlocal processed, errors
        subject = msg.subject

        try:
            payload = json.loads(msg.data.decode())

            if not isinstance(payload, dict):
                logger.warning("Received non-object JSON on %s — skipping", subject)
                errors += 1
                return

            if not _validate_decoded_packet(payload):
                logger.warning("Invalid decoded packet structure on %s", subject)
                errors += 1
                return

            super_nodes = payload.get("super_nodes", [])
            control_plane = payload.get("control_plane", {})
            source_spec = payload.get("source_spec", "unknown")

            node_count = len(super_nodes)
            cp_keys = list(control_plane.keys())[:5]

            logger.info(
                "Decoded packet: source=%s, super_nodes=%d, control_plane_keys=%s",
                source_spec,
                node_count,
                cp_keys,
            )

            # Log geometry data for observability (future: route to downstream subjects)
            for node in super_nodes:
                node_id = node.get("id", "unknown")
                constellations = node.get("constellations", [])
                for constellation in constellations:
                    points = constellation.get("points", [])
                    logger.debug(
                        "  node=%s constellation=%s points=%d",
                        node_id,
                        constellation.get("id", "?"),
                        len(points),
                    )

            processed += 1

        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from message on %s", subject)
            errors += 1
        except Exception as e:
            logger.error("Error processing message on %s: %s", subject, e)
            errors += 1

    await nc.subscribe(subscribe_subject, cb=message_handler)
    logger.info("Subscribed to %s", subscribe_subject)

    # Graceful shutdown
    stop_event = asyncio.Event()

    def _signal_handler(*_):
        logger.info("Shutdown signal received")
        stop_event.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    try:
        await stop_event.wait()
    finally:
        logger.info("Processed=%d Errors=%d — closing NATS", processed, errors)
        await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
