"""NATS consumer for the Tokenism Simulator (O-2a).

Subscribes to the canonical CHIT geometry subject ``geometry.cgp.v1`` (published
by the flute-gateway voice synthesis pipeline and other CGP producers via the
``GeometryBridge``) using a JetStream durable consumer. For each CGP packet
received, the consumer extracts the BPM value from the prosodic payload and
republishes a flattened event on ``tokenism.prosodic.bpm.v1`` for downstream
BPM consumers (rhythm tracker, chakra band telemetry, persona signature).

Design notes
------------
- The subscriber runs in a background asyncio loop launched from a daemon
  thread inside ``app.py``. We never block the Flask app startup on NATS
  availability — if NATS is unreachable, we log a warning and keep retrying.
- BPM extraction is defensive: it probes multiple known field paths in the
  CGP v0.2 schema produced by flute-gateway's ``encode_bpm_timeline`` plus
  a couple of legacy/flat shapes, defaulting to ``0`` if none are present.
- We attempt a JetStream durable consumer first (``tokenism-cgp-consumer``).
  If JetStream is not enabled or the ``geometry.cgp.v1`` subject is not
  bound to a stream in this NATS deployment, we fall back to a core NATS
  push subscription so we still see events in non-JetStream environments.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
from typing import Any, Optional

import nats
from nats.aio.client import Client as NATS
from nats.aio.msg import Msg
from nats.errors import NoServersError, TimeoutError as NATSTimeoutError
from nats.js.errors import NotFoundError as JSNotFoundError

logger = logging.getLogger(__name__)

# Subjects ------------------------------------------------------------------
CGP_SUBJECT = os.environ.get("TOKENISM_CGP_SUBJECT", "geometry.cgp.v1")
BPM_OUT_SUBJECT = os.environ.get(
    "TOKENISM_BPM_SUBJECT", "tokenism.prosodic.bpm.v1"
)
DURABLE_NAME = os.environ.get(
    "TOKENISM_CGP_DURABLE", "tokenism-cgp-consumer"
)

# Identity ------------------------------------------------------------------
NODE_ID = os.environ.get("NODE_ID") or os.environ.get(
    "PMOVES_NODE_ID", socket.gethostname()
)

# Retry policy --------------------------------------------------------------
_RECONNECT_BACKOFF_SECONDS = 5.0


def _extract_bpm(payload: dict[str, Any]) -> float:
    """Best-effort BPM extraction from a CGP packet.

    Probes (in order):
        1. ``data.bpm`` / ``data.prosodic.bpm`` / ``data.meta.bpm`` — for
           envelope-wrapped publishers (e.g. our own NATSClient wrapper).
        2. Top-level ``bpm`` / ``prosodic.bpm`` / ``meta.bpm`` /
           ``meta.avg_bpm``.
        3. CGP v0.2 prosodic shape:
           ``super_nodes[0].constellations[0].meta.avg_bpm``.
        4. Per-point fallback: first point's ``meta.bpm`` under the same
           constellation.

    Returns 0.0 if no usable BPM field is found.
    """
    if not isinstance(payload, dict):
        return 0.0

    # 1. Envelope-wrapped data (matches NATSClient.publish in config/nats.py)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else None
    for source in (data, payload):
        if not isinstance(source, dict):
            continue
        for key in ("bpm", "avg_bpm"):
            val = source.get(key)
            if isinstance(val, (int, float)) and val > 0:
                return float(val)
        prosodic = source.get("prosodic")
        if isinstance(prosodic, dict):
            val = prosodic.get("bpm") or prosodic.get("avg_bpm")
            if isinstance(val, (int, float)) and val > 0:
                return float(val)
        meta = source.get("meta")
        if isinstance(meta, dict):
            val = meta.get("bpm") or meta.get("avg_bpm")
            if isinstance(val, (int, float)) and val > 0:
                return float(val)

    # 2. CGP v0.2 prosodic shape from flute-gateway bpm_encoder
    super_nodes = payload.get("super_nodes")
    if isinstance(super_nodes, list) and super_nodes:
        first_sn = super_nodes[0]
        if isinstance(first_sn, dict):
            constellations = first_sn.get("constellations")
            if isinstance(constellations, list) and constellations:
                first_const = constellations[0]
                if isinstance(first_const, dict):
                    cmeta = first_const.get("meta")
                    if isinstance(cmeta, dict):
                        val = cmeta.get("avg_bpm") or cmeta.get("bpm")
                        if isinstance(val, (int, float)) and val > 0:
                            return float(val)
                    points = first_const.get("points")
                    if isinstance(points, list) and points:
                        first_point = points[0]
                        if isinstance(first_point, dict):
                            pmeta = first_point.get("meta")
                            if isinstance(pmeta, dict):
                                val = pmeta.get("bpm")
                                if isinstance(val, (int, float)) and val > 0:
                                    return float(val)

    return 0.0


def _extract_source_agent(payload: dict[str, Any]) -> str:
    """Pull the publishing-service identifier from a CGP packet, if any."""
    if not isinstance(payload, dict):
        return ""
    # CGP v0.2 canonical: meta.source
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else None
    if meta and isinstance(meta.get("source"), str):
        return meta["source"]
    # Envelope-wrapped (NATSClient.publish in this service)
    if isinstance(payload.get("source"), str):
        return payload["source"]
    # Persona/agent fallbacks
    if meta and isinstance(meta.get("voice_persona_id"), str):
        return meta["voice_persona_id"]
    return ""


async def _handle_cgp_message(nc: NATS, msg: Msg) -> None:
    """Decode a CGP packet, extract BPM, and republish a flat BPM event."""
    try:
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning(
                "tokenism nats_consumer: malformed CGP payload on %s — %s",
                msg.subject,
                exc,
            )
            # Still ack JetStream messages so the consumer doesn't loop.
            await _try_ack(msg)
            return

        bpm = _extract_bpm(payload)
        source_agent = _extract_source_agent(payload)

        out_event = {
            "node_id": NODE_ID,
            "bpm": bpm,
            "ts": int(time.time()),
            "source_agent": source_agent,
        }

        try:
            await nc.publish(
                BPM_OUT_SUBJECT,
                json.dumps(out_event).encode("utf-8"),
            )
            logger.debug(
                "tokenism nats_consumer: republished BPM=%s source=%s -> %s",
                bpm,
                source_agent,
                BPM_OUT_SUBJECT,
            )
        except Exception as exc:  # noqa: BLE001 — best-effort republish
            logger.warning(
                "tokenism nats_consumer: failed to publish %s — %s",
                BPM_OUT_SUBJECT,
                exc,
            )

        await _try_ack(msg)

    except Exception as exc:  # noqa: BLE001 — never let a bad msg kill the loop
        logger.exception(
            "tokenism nats_consumer: unexpected error handling %s — %s",
            msg.subject,
            exc,
        )


async def _try_ack(msg: Msg) -> None:
    """Ack a JetStream message; no-op for core NATS push subs."""
    try:
        await msg.ack()
    except Exception:
        # Core NATS push subscriptions don't expose ack(); ignore.
        pass


async def _run_once(nats_url: str) -> None:
    """One end-to-end NATS session. Returns when the connection drops."""
    logger.info(
        "tokenism nats_consumer: connecting to NATS at %s (durable=%s, subject=%s)",
        nats_url,
        DURABLE_NAME,
        CGP_SUBJECT,
    )

    nc: NATS = await nats.connect(
        servers=nats_url,
        name=os.environ.get("NATS_CLIENT_NAME", "tokenism-simulator"),
        connect_timeout=10,
        reconnect_time_wait=2,
        max_reconnect_attempts=-1,
    )

    async def cb(msg: Msg) -> None:
        await _handle_cgp_message(nc, msg)

    subscribed_via_js = False

    # Prefer JetStream durable consumer when available.
    if os.environ.get("NATS_JETSTREAM", "true").lower() == "true":
        try:
            js = nc.jetstream()
            await js.subscribe(
                CGP_SUBJECT,
                durable=DURABLE_NAME,
                cb=cb,
                manual_ack=True,
            )
            subscribed_via_js = True
            logger.info(
                "tokenism nats_consumer: JetStream durable subscription active "
                "(durable=%s, subject=%s)",
                DURABLE_NAME,
                CGP_SUBJECT,
            )
        except (JSNotFoundError, NATSTimeoutError) as exc:
            logger.warning(
                "tokenism nats_consumer: JetStream subscribe failed (%s) — "
                "falling back to core NATS",
                exc,
            )
        except Exception as exc:  # noqa: BLE001 — keep service alive
            logger.warning(
                "tokenism nats_consumer: JetStream init error (%s) — "
                "falling back to core NATS",
                exc,
            )

    if not subscribed_via_js:
        await nc.subscribe(CGP_SUBJECT, cb=cb)
        logger.info(
            "tokenism nats_consumer: core NATS subscription active (subject=%s)",
            CGP_SUBJECT,
        )

    # Block until the connection closes. We deliberately don't use a
    # `while True: sleep` here so a clean disconnect propagates fast.
    try:
        while nc.is_connected:
            await asyncio.sleep(1.0)
    finally:
        try:
            await nc.drain()
        except Exception:
            pass


async def start_nats_consumer(nats_url: Optional[str] = None) -> None:
    """Run the CGP -> BPM consumer loop forever, with retry on failures.

    Intended to be invoked via ``asyncio.run`` from a daemon thread spawned
    by ``app.py`` at Flask startup. Connection failures (NATS down, auth
    rejected, network blips) are logged at WARNING and the loop sleeps for
    ``_RECONNECT_BACKOFF_SECONDS`` before retrying. This function never
    raises to the caller — it owns its own error envelope.
    """
    url = nats_url or os.environ.get(
        "NATS_URL", "nats://nats:pmoves@nats:4222"
    )

    while True:
        try:
            await _run_once(url)
            logger.info(
                "tokenism nats_consumer: NATS session ended cleanly, reconnecting in %.1fs",
                _RECONNECT_BACKOFF_SECONDS,
            )
        except NoServersError as exc:
            logger.warning(
                "tokenism nats_consumer: no NATS servers reachable (%s); "
                "retrying in %.1fs",
                exc,
                _RECONNECT_BACKOFF_SECONDS,
            )
        except asyncio.CancelledError:
            logger.info("tokenism nats_consumer: cancelled, exiting")
            raise
        except Exception as exc:  # noqa: BLE001 — keep the service alive
            logger.warning(
                "tokenism nats_consumer: session error (%s); retrying in %.1fs",
                exc,
                _RECONNECT_BACKOFF_SECONDS,
            )

        await asyncio.sleep(_RECONNECT_BACKOFF_SECONDS)
