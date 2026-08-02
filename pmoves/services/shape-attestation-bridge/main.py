#!/usr/bin/env python3
"""Shape Attestation Bridge — closes the raw→shaped→attested→HiRAG pipeline.

Subscribes to content.lexicon.shaped.v1 (published by spark-shape-worker and
content-provenance-gate), CHIT-signs each packet, and republishes to:
  - content.provenance.attested.v1 (CHIT-attested shaped packets)
  - content.hirag.accepted.v1 (ready for HiRAG indexing)

This bridges the gap where spark-shape-worker publishes shaped packets but
nobody attests them or forwards to HiRAG.

Pipeline: raw → shaped (spark-shape-worker) → attested (this bridge) → accepted → HiRAG
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import signal
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from nats.aio.client import Client as NATS

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _load_secret(key: str, default: str = "") -> str:
    val = os.environ.get(key)
    if val:
        return val
    file_path = os.environ.get(f"{key}_FILE")
    if file_path and os.path.exists(file_path):
        with open(file_path, encoding="utf-8") as fh:
            return fh.read().strip()
    return default


def _resolve_nats_url() -> str:
    url = _load_secret("NATS_URL")
    if url:
        return url
    host = os.environ.get("NATS_HOST", "nats")
    port = os.environ.get("NATS_PORT", "4222")
    return f"nats://{host}:{port}"


def _redact_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        if parsed.password:
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
            return url.replace(parsed.netloc, netloc)
    except Exception:
        pass
    return url


def _chit_attest(payload: dict, passphrase: str) -> dict:
    """CHIT HMAC-SHA256 attestation for shaped content packets."""
    ts = datetime.now(timezone.utc).isoformat()
    attest_id = str(uuid.uuid4())
    payload["attestation"] = {
        "id": attest_id,
        "timestamp": ts,
        "agent": "shape-attestation-bridge",
        "node": os.environ.get("PMOVES_NODE_ID", "unknown"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(passphrase.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    payload["attestation"]["sig"] = {
        "alg": "HMAC-SHA256",
        "kid": "shape-attestation-bridge",
        "hmac": sig,
    }
    return payload


def _build_accepted_packet(attested: dict) -> dict:
    """Build HiRAG accepted packet preserving all content contract fields."""
    packet = {
        "id": attested.get("id", f"hirag-accept-{attested.get('attestation', {}).get('id', str(uuid.uuid4())[:8])}"),
        "timestamp": attested.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "source": {
            "agent": "shape-attestation-bridge",
            "original_source": attested.get("source", {}),
        },
        "attestation": attested.get("attestation", {}),
        "hirag_namespace": os.environ.get("HIRAG_NAMESPACE", "default"),
        "status": "accepted",
    }
    # Preserve all content contract fields from the shaped packet
    for key in ("content", "lexicon", "anchors", "semantic_density", "noise_score", "metadata"):
        if key in attested:
            packet[key] = attested[key]
    return packet


async def main():
    nc = NATS()
    nats_url = _resolve_nats_url()
    chit_passphrase = _load_secret("CHIT_PASSPHRASE")
    sub_subject = os.environ.get("ATTEST_SUBSCRIBE_SUBJECT", "content.lexicon.shaped.v1")
    attested_subject = os.environ.get("ATTESTED_SUBJECT", "content.provenance.attested.v1")
    accepted_subject = os.environ.get("ACCEPTED_SUBJECT", "content.hirag.accepted.v1")
    strict_mode = bool(chit_passphrase)
    processed = 0
    attested_count = 0
    errors = 0

    try:
        await nc.connect(nats_url, connect_timeout=10)
        logger.info("Connected to NATS at %s", _redact_url(nats_url))
        logger.info("CHIT strict mode: %s", strict_mode)
    except Exception as e:
        logger.error("Failed to connect to NATS: %s", type(e).__name__)
        return

    async def message_handler(msg):
        nonlocal processed, attested_count, errors
        try:
            payload = json.loads(msg.data.decode())
            if not isinstance(payload, dict):
                logger.warning("Non-object JSON on %s — skipping", msg.subject)
                errors += 1
                return

            # CHIT attest the shaped packet
            if chit_passphrase:
                attested = _chit_attest(payload.copy(), chit_passphrase)
                attested_count += 1
            else:
                logger.debug("CHIT_PASSPHRASE not set — forwarding unsigned (advisory mode)")
                attested = payload

            # Publish attested packet
            await nc.publish(attested_subject, json.dumps(attested, default=str).encode())

            # Build and publish accepted packet for HiRAG
            accepted = _build_accepted_packet(attested)
            await nc.publish(accepted_subject, json.dumps(accepted, default=str).encode())

            processed += 1
            shaped_id = payload.get("id", "unknown")
            logger.info("Attested %s → %s + %s", shaped_id, attested_subject, accepted_subject)

        except json.JSONDecodeError:
            logger.error("JSON decode error on %s", msg.subject)
            errors += 1
        except Exception as e:
            logger.error("Error attesting packet: %s", type(e).__name__)
            errors += 1

    await nc.subscribe(sub_subject, cb=message_handler)
    logger.info("Subscribed to %s, publishing to %s + %s", sub_subject, attested_subject, accepted_subject)

    stop_event = asyncio.Event()
    def _signal_handler(*_):
        stop_event.set()
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    try:
        await stop_event.wait()
    finally:
        logger.info("Processed=%d Attested=%d Errors=%d — closing", processed, attested_count, errors)
        await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
