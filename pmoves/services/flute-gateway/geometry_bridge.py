"""GeometryBridge: wrap voice-synthesis events into CHIT CGP v0.2 packets.

Flute already publishes a flat voice-synthesis event to the legacy subject
`tokenism.geometry.event.v1`. This bridge wraps the same data into a
schema-valid CGP v0.2 packet (per `contracts/schemas/geometry/cgp.v2.schema.json`)
and signs it via HMAC-SHA256 so it can be published to the canonical
`geometry.cgp.v1` subject for new consumers (matrix monitor, cymatic
visualizer, persona signature broadcast).

Closes issue #1397.

Dual-publish migration: callers should keep publishing the legacy event
unchanged AND publish this CGP-wrapped variant in parallel. The kill-switch
is `FLUTE_GEOMETRY_DUAL_PUBLISH=false`.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from chit_signing import sign_cgp, verify_cgp

logger = logging.getLogger(__name__)

CGP_SPEC = "chit.cgp.v0.2"


class GeometryBridge:
    """Encode voice-synthesis events into signed CGP v0.2 packets.

    The bridge does not own NATS publishing — it only produces packets.
    The caller (flute-gateway main.py) is responsible for publishing the
    returned dict on `FLUTE_CGP_SUBJECT` (default `geometry.cgp.v1`).
    """

    def __init__(self, passphrase: Optional[str] = None) -> None:
        """Construct with an optional explicit signing passphrase.

        If `passphrase` is None, the bridge falls back to the env-resolved
        key at sign time (CHIT_SIGNING_KEY → CHIT_PASSPHRASE). This matches
        the canonical `pmoves.tools.chit_security` priority order.
        """
        self._passphrase = passphrase

    def encode_packet(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap a flat voice-synthesis event into a signed CGP v0.2 packet.

        Input shape (matches the existing `_publish_chit_voice_event` payload):

            {
              "namespace": "pmoves.voice",
              "modality": "voice_synthesis",
              "provider": "vibevoice",
              "text_length": 142,
              "audio_duration_seconds": 8.4,
              "voice": "alloy",
              "ts": "2026-04-27T...Z",
            }

        Output shape: a `chit.cgp.v0.2` packet with the event embedded as a
        single point under one constellation under one super_node, plus an
        HMAC `sig` block.

        If no signing key is available in env or constructor, the packet is
        returned **unsigned** (no `sig` block) and a warning is logged. This
        matches the dev-mode pattern used by `sign_trail` in the rest of
        PMOVES.
        """
        ts = event.get("ts") or datetime.now(timezone.utc).isoformat()

        # Deep copy meta — strip the keys we promote to point fields
        meta = {
            k: v
            for k, v in event.items()
            if k not in {"ts", "modality", "text_length"}
        }

        point: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "modality": event.get("modality", "voice_synthesis"),
            "ts": ts,
            "meta": meta,
        }
        text_length = event.get("text_length")
        if isinstance(text_length, int) and text_length >= 0:
            point["char_len"] = text_length

        cgp: Dict[str, Any] = {
            "spec": CGP_SPEC,
            "summary": "Voice synthesis event from flute-gateway",
            "created_at": ts,
            "super_nodes": [
                {
                    "id": "voice-synthesis",
                    "label": "Flute Voice Synthesis",
                    "constellations": [
                        {
                            "id": "voice-events",
                            "points": [point],
                        }
                    ],
                }
            ],
        }

        # Best-effort sign. Missing key → return unsigned with warning.
        try:
            return sign_cgp(cgp, passphrase=self._passphrase)
        except RuntimeError as exc:
            logger.warning(
                "geometry_bridge: returning unsigned packet — %s", exc
            )
            return cgp

    def verify_packet(self, cgp: Dict[str, Any]) -> bool:
        """Verify the HMAC signature on a packet (used by tests)."""
        return verify_cgp(cgp, passphrase=self._passphrase)


def is_dual_publish_enabled() -> bool:
    """Return True if `FLUTE_GEOMETRY_DUAL_PUBLISH` is unset or truthy.

    Default is True (publish to canonical subject as well as legacy).
    Kill-switch: set the env var to `false`/`0`/`no` to disable.
    """
    val = os.environ.get("FLUTE_GEOMETRY_DUAL_PUBLISH", "true").strip().lower()
    return val not in {"false", "0", "no", "off"}


def cgp_subject() -> str:
    """Return the canonical CGP subject (overridable for testing)."""
    return os.environ.get("FLUTE_CGP_SUBJECT", "geometry.cgp.v1")
