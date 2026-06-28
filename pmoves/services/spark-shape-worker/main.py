#!/usr/bin/env python3
"""PMOVES SPARK Shape Worker.

Subscribes to GPU inference results on the NATS mesh, attests them,
and re-emits shaped content packets for provenance-aware downstream consumers
(HiRAG ingest, Hyperdimensions replay/control).

Subjects:
  Subscribe : mesh.gpu.inference.result.v1
  Publish   : content.lexicon.shaped.v1
  Publish   : mesh.shape.handshake.v1

The worker is intentionally small and stateless. It can run as a sidecar
container, a systemd service on the DGX Spark GB10 host, or a one-shot
process during bring-up validation.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

import nats
from nats.aio.client import Client as NATS

NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
SHAPE_SECRET = os.environ.get("SPARK_SHAPE_SECRET", "")

SUBSCRIBE_SUBJECT = "mesh.gpu.inference.result.v1"
PUBLISH_SHAPED = "content.lexicon.shaped.v1"
PUBLISH_HANDSHAKE = "mesh.shape.handshake.v1"


class ShapeWorker:
    def __init__(self, nats_url: str, shape_secret: str) -> None:
        self.nats_url = nats_url
        self.shape_secret = shape_secret
        self.nc: NATS | None = None
        self.sub = None
        self._shutdown = asyncio.Event()

    def _attestation(self, payload: dict[str, Any]) -> tuple[bool, str]:
        """Produce a deterministic attestation signature for the shaped packet.

        When SPARK_SHAPE_SECRET is unset the payload is still emitted but marked
        unattested. Consumers that gate on attestation should reject
        unattested packets.
        """
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
        if not self.shape_secret:
            return False, ""
        digest = hmac.new(
            self.shape_secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return True, digest

    def _shape(self, raw_message: dict[str, Any]) -> dict[str, Any]:
        """Transform a GPU inference result into a shaped content packet."""
        now = datetime.now(timezone.utc).isoformat()
        content_id = str(uuid.uuid4())
        shaped: dict[str, Any] = {
            "content_id": content_id,
            "envelope_type": "content.lexicon.shaped.v1",
            "source_subject": SUBSCRIBE_SUBJECT,
            "source_node": raw_message.get("node_id") or raw_message.get("node", "unknown"),
            "source_model": raw_message.get("model_id", "unknown"),
            "request_id": raw_message.get("request_id", "unknown"),
            "shaped_at": now,
            "inference": {
                "prompt_tokens": raw_message.get("prompt_tokens", 0),
                "completion_tokens": raw_message.get("completion_tokens", 0),
                "duration_ms": raw_message.get("duration_ms", 0),
            },
            "summary": self._summarize(raw_message.get("result") or raw_message.get("output")),
        }
        attested, signature = self._attestation(shaped)
        shaped["attested"] = attested
        shaped["signature"] = signature
        return shaped

    @staticmethod
    def _summarize(result: Any) -> dict[str, Any]:
        """Create a lightweight summary for provenance indexing.

        Keeps the shaped packet small while preserving enough structure for
        downstream replay/control surfaces to route it.
        """
        if result is None:
            return {"kind": "empty"}
        if isinstance(result, str):
            return {"kind": "text", "preview": result[:240]}
        if isinstance(result, dict):
            return {"kind": "object", "keys": list(result.keys())[:20]}
        return {"kind": "other", "type": type(result).__name__}

    async def _on_result(self, msg) -> None:
        try:
            raw = json.loads(msg.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"[shape-worker] dropping non-JSON message: {exc}", file=sys.stderr)
            return

        shaped = self._shape(raw)
        data = json.dumps(shaped, default=str).encode("utf-8")

        await self.nc.publish(PUBLISH_SHAPED, data)
        print(f"[shape-worker] emitted {PUBLISH_SHAPED} content_id={shaped['content_id']}")

        handshake = {
            "handshake_id": str(uuid.uuid4()),
            "content_id": shaped["content_id"],
            "envelope_type": "mesh.shape.handshake.v1",
            "source_subject": SUBSCRIBE_SUBJECT,
            "attested": shaped["attested"],
            "shaped_at": shaped["shaped_at"],
        }
        await self.nc.publish(PUBLISH_HANDSHAKE, json.dumps(handshake, default=str).encode("utf-8"))
        print(f"[shape-worker] emitted {PUBLISH_HANDSHAKE} content_id={shaped['content_id']}")

    async def run(self) -> int:
        self.nc = await nats.connect(self.nats_url)
        self.sub = await self.nc.subscribe(SUBSCRIBE_SUBJECT, cb=self._on_result)
        print(f"[shape-worker] connected to {self.nats_url}")
        print(f"[shape-worker] subscribed to {SUBSCRIBE_SUBJECT}")

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown.set)

        await self._shutdown.wait()
        await self.sub.unsubscribe()
        await self.nc.drain()
        print("[shape-worker] shutdown complete")
        return 0

    def _shutdown_now(self) -> None:
        if not self._shutdown.is_set():
            self._shutdown.set()


async def main() -> int:
    worker = ShapeWorker(NATS_URL, SHAPE_SECRET)
    return await worker.run()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
