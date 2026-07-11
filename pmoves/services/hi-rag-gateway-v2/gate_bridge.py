"""Gate -> publish bridge core (PR B). Pure: no NATS, no geometry_bus imports.

On a gate-open event, enforce the fail-closed egress floor, and only on a clean
verdict return the content.publish.approved.v1 payload. Any problem -> None (hold).
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("hirag.gate_bridge")

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
    except Exception:
        logger.exception("gate-hold: floor raised (fail-closed)")
        return None

    if not verdict.clean:
        logger.warning("gate-hold: egress floor tripped %s for %s", verdict.tripped, artifact_uri)
        return None

    approval = {"artifact_uri": artifact_uri, "title": title}
    for key in _PASSTHROUGH:
        if key in payload and payload[key] is not None:
            approval[key] = payload[key]
    approved_by = payload.get("approved_by")
    if isinstance(approved_by, str) and approved_by:
        approval["approved_by"] = approved_by
    return approval
