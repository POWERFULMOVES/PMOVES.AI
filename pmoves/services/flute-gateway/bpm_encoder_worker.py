#!/usr/bin/env python3
# Runtime: Run as a standalone sidecar alongside spark-shape-worker or flute-gateway.
"""BPM Encoder Worker — subscribes to mesh.gpu.inference.result.v1.

Encodes prosodic BPM profiles from GPU inference results and publishes
CGP v0.2 packets to bpm.encoded.v1 on the NATS mesh.

Follows spark-shape-worker pattern: asyncio, nats.aio.client, HMAC attestation.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import signal
import sys
import uuid
from datetime import datetime, timezone
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

BOUNDARY_BPM = {
    "SENTENCE": 60,
    "CLAUSE": 90,
    "PHRASE": 120,
    "BREATH": 80,
    "NONE": 150,
}

_BOUNDARY_RE = re.compile(r'[.!?;,:]\s*')


def _resolve_nats_url() -> str:
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


def _extract_text(payload: dict) -> str:
    result = payload.get("result", {})
    if isinstance(result, dict):
        text = result.get("response") or result.get("text") or result.get("output", "")
        if isinstance(text, str):
            return text
    return str(result)


def _detect_boundaries(text: str) -> list[dict]:
    boundaries = []
    for match in _BOUNDARY_RE.finditer(text):
        boundary_type = "SENTENCE" if match.group().rstrip() in ".!?" else "CLAUSE" if match.group().rstrip() in ";" else "PHRASE"
        boundaries.append({"position": match.start(), "type": boundary_type, "bpm": BOUNDARY_BPM[boundary_type]})
        match.end()
    if not boundaries:
        boundaries.append({"position": len(text), "type": "NONE", "bpm": BOUNDARY_BPM["NONE"]})
    return boundaries


def _encode_prosodic_profile(text: str) -> dict:
    boundaries = _detect_boundaries(text)
    chunks = []
    prev_pos = 0
    for b in boundaries:
        chunk_text = text[prev_pos:b["position"]].strip()
        if chunk_text:
            chunks.append({
                "text": chunk_text,
                "boundary": b["type"],
                "bpm": b["bpm"],
                "start_char": prev_pos,
                "end_char": b["position"],
            })
        prev_pos = b["position"] + 1
    # Capture trailing text after last boundary
    if prev_pos < len(text):
        trailing = text[prev_pos:].strip()
        if trailing:
            chunks.append({"text": trailing, "boundary": "NONE", "bpm": BOUNDARY_BPM["NONE"], "start_char": prev_pos, "end_char": len(text)})
    avg_bpm = sum(c["bpm"] for c in chunks) / len(chunks) if chunks else BOUNDARY_BPM["NONE"]
    return {"chunks": chunks, "avg_bpm": round(avg_bpm, 1), "total_chunks": len(chunks)}


def _build_cgp_packet(profile: dict, source: dict) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    packet_id = str(uuid.uuid4())
    packet = {
        "spec": "chit.cgp.v0.2",
        "id": packet_id,
        "timestamp": ts,
        "source": {
            "agent": "bpm-encoder-worker",
            "node": os.environ.get("PMOVES_NODE_ID", "unknown"),
            "inference_model": source.get("model", "unknown"),
        },
        "control_plane": {
            "avg_bpm": profile["avg_bpm"],
            "total_chunks": profile["total_chunks"],
            "encoding_version": "1.0",
        },
        "super_nodes": [
            {
                "id": f"bpm_{packet_id[:8]}",
                "type": "prosodic_bpm",
                "constellations": [
                    {
                        "id": f"chunk_{i}",
                        "type": "prosodic_chunk",
                        # One CGP point per prosodic chunk. The schema's point
                        # requires `id`; prosodic attributes ride in `meta` so
                        # the packet validates against cgp.v2.schema.json.
                        "points": [
                            {
                                "id": f"chunk_{i}_pt",
                                "text": c["text"][:200],
                                "meta": {
                                    "boundary": c["boundary"],
                                    "bpm": c["bpm"],
                                },
                            }
                        ],
                    }
                    for i, c in enumerate(profile["chunks"])
                ],
            }
        ],
    }
    secret = _load_secret("BPM_ENCODER_SECRET")
    if secret:
        canonical = json.dumps(packet, sort_keys=True, separators=(",", ":"))
        sig = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        packet["attestation"] = {"algorithm": "HMAC-SHA256", "signature": sig}
    return packet


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

    sub_subject = os.environ.get("BPM_ENCODER_SUBSCRIBE_SUBJECT", "mesh.gpu.inference.result.v1")
    pub_subject = os.environ.get("BPM_ENCODER_PUBLISH_SUBJECT", "bpm.encoded.v1")
    processed = 0
    errors = 0

    async def message_handler(msg):
        nonlocal processed, errors
        try:
            payload = json.loads(msg.data.decode())
            text = _extract_text(payload)
            if not text:
                logger.warning("No text in inference result — skipping")
                errors += 1
                return
            profile = _encode_prosodic_profile(text)
            packet = _build_cgp_packet(profile, payload)
            await nc.publish(pub_subject, json.dumps(packet).encode())
            processed += 1
            logger.info("Encoded BPM profile: chunks=%d avg_bpm=%.1f → %s", profile["total_chunks"], profile["avg_bpm"], pub_subject)
        except Exception as e:
            logger.error("Error encoding BPM: %s", e)
            errors += 1

    await nc.subscribe(sub_subject, cb=message_handler)
    logger.info("Subscribed to %s, publishing to %s", sub_subject, pub_subject)

    stop_event = asyncio.Event()
    def _signal_handler(*_):
        stop_event.set()
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    try:
        await stop_event.wait()
    finally:
        logger.info("Processed=%d Errors=%d — closing", processed, errors)
        await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
