"""Gate -> publish bridge core (PR B). Pure: no NATS, no geometry_bus imports.

On a gate-open event, enforce the fail-closed egress floor, and only on a clean
verdict return the content.publish.approved.v1 payload. Any problem -> None (hold).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger("hirag.gate_bridge")

APPROVED_SUBJECT = "content.publish.approved.v1"
GATE_SUBJECT = "geometry.publish.gate.v1"

_PASSTHROUGH = ("namespace", "tags", "description", "meta", "studio_board_id")


def handle_gate_event(payload: dict, floor) -> Optional[dict]:
    if not isinstance(payload, dict):
        return None
    artifact_uri = payload.get("artifact_uri")
    title = payload.get("title")
    if not isinstance(artifact_uri, str) or not artifact_uri.startswith("s3://"):
        logger.warning("gate-hold: missing/invalid artifact_uri")
        return None
    if not isinstance(title, str) or not title.strip():
        logger.warning("gate-hold: missing title")
        return None

    try:
        verdict = floor.check(payload)
        clean = bool(verdict.clean)
    except Exception:
        logger.exception("gate-hold: floor raised or returned malformed verdict (fail-closed)")
        return None

    if not clean:
        logger.warning("gate-hold: egress floor tripped %s for %s", getattr(verdict, "tripped", "?"), artifact_uri)
        return None

    approval = {"artifact_uri": artifact_uri, "title": title}
    for key in _PASSTHROUGH:
        if key in payload and payload[key] is not None:
            approval[key] = payload[key]
    approved_by = payload.get("approved_by")
    if isinstance(approved_by, str) and approved_by:
        approval["approved_by"] = approved_by
    return approval


async def _dispatch(msg_data: bytes, floor, publish) -> bool:
    """Decode a gate event, run the core, publish approval if clean. Returns True
    iff an approval was published. `publish` is an async callable(subject, bytes)."""
    try:
        decoded = json.loads(msg_data.decode())
    except Exception:
        logger.warning("gate-hold: invalid geometry.publish.gate.v1 payload")
        return False
    payload = decoded.get("payload") if isinstance(decoded, dict) and isinstance(decoded.get("payload"), dict) else decoded
    approval = handle_gate_event(payload, floor)
    if approval is None:
        return False
    await publish(APPROVED_SUBJECT, json.dumps(approval).encode())
    logger.info("gate-open: published %s for %s", APPROVED_SUBJECT, approval.get("artifact_uri"))
    return True


async def publish_gate_worker(nats_url: str, room_manifest_path: str, backoff: float = 5.0) -> None:
    """Mirror of _content_provenance_worker: subscribe GATE_SUBJECT, run _dispatch."""
    import nats  # local import keeps module NATS-free for tests
    from egress_floor import load_floor

    floor = load_floor(room_manifest_path)
    while True:
        try:
            nc = await nats.connect(servers=[nats_url])

            async def _handler(msg):
                await _dispatch(msg.data, floor, nc.publish)

            await nc.subscribe(GATE_SUBJECT, cb=_handler)
            logger.info("pub-gate bridge listening on %s", GATE_SUBJECT)
            # keep the task alive
            import asyncio as _asyncio
            await _asyncio.Event().wait()
        except Exception:
            logger.exception("pub-gate bridge error; retry in %.1fs", backoff)
            import asyncio as _asyncio
            await _asyncio.sleep(backoff)
