#!/usr/bin/env python3
"""PMOVES SPARK Shape Worker.

Subscribes to GPU inference results on the NATS mesh and emits:

- `content.lexicon.shaped.v1` packets matching the service schema contract
  (`pmoves/contracts/schemas/content/lexicon.shaped.v1.schema.json`).
- `mesh.shape.handshake.v1` shape-capsule envelopes matching the contract
  expected by `pmoves/services/mesh-agent/main.py`.

The worker is intentionally small and stateless. It can run as a sidecar
container, a systemd service on the DGX Spark GB10 host, or a one-shot
process during bring-up validation.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import signal
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

import nats
from nats.aio.client import Client as NATS


def _secret(key: str, default: str = "") -> str:
    """Read {key} from env, falling back to the {key}_FILE mount (Docker secret convention)."""
    val = os.environ.get(key)
    if val:
        return val
    file_path = os.environ.get(f"{key}_FILE")
    if file_path and os.path.exists(file_path):
        with open(file_path, encoding="utf-8") as fh:
            return fh.read().strip()
    return default


def _redact_url(url: str) -> str:
    """Strip embedded credentials (user:pass@) from a connection URL for logging."""
    if "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            return f"{scheme}://***@{rest.split('@', 1)[1]}"
    return url


NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
SHAPE_SECRET = _secret("SPARK_SHAPE_SECRET", "")
MESH_PASSPHRASE = _secret("MESH_PASSPHRASE", "")

SUBSCRIBE_SUBJECT = "mesh.gpu.inference.result.v1"
PUBLISH_SHAPED = "content.lexicon.shaped.v1"
PUBLISH_HANDSHAKE = "mesh.shape.handshake.v1"


class ShapeWorker:
    def __init__(self, nats_url: str, shape_secret: str, mesh_passphrase: str) -> None:
        self.nats_url = nats_url
        self.shape_secret = shape_secret
        self.mesh_passphrase = mesh_passphrase
        self.nc: NATS | None = None
        self.sub = None
        self._shutdown = asyncio.Event()

    @staticmethod
    def _canon(obj: Any) -> bytes:
        """Canonical JSON encoding used by mesh-agent for HMAC verification."""
        return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _attestation(self, payload: dict[str, Any]) -> str:
        """Produce a deterministic HMAC-SHA256 signature for a shaped packet.

        Returns an empty string when SPARK_SHAPE_SECRET is unset.
        """
        if not self.shape_secret:
            return ""
        digest = hmac.new(
            self.shape_secret.encode("utf-8"),
            self._canon(payload),
            hashlib.sha256,
        ).hexdigest()
        return digest

    @staticmethod
    def _extract_text(raw_message: dict[str, Any]) -> str:
        """Extract a non-empty text representation from the inference result."""
        result = raw_message.get("result") or raw_message.get("output")
        if isinstance(result, str) and result.strip():
            return result.strip()
        if isinstance(result, (list, dict)):
            text = json.dumps(result, ensure_ascii=False, default=str)
            if text:
                return text
        # Fall back to prompt text if no result is present.
        prompt = raw_message.get("prompt", "")
        if isinstance(prompt, str) and prompt.strip():
            return prompt.strip()
        return "(no text)"

    @staticmethod
    def _extract_terms(text: str, limit: int = 10) -> list[str]:
        """Extract a small set of anchor terms from text."""
        lowered = text.lower()
        tokens = re.findall(r"[a-z][a-z0-9]*", lowered)
        seen: set[str] = set()
        terms: list[str] = []
        for token in tokens:
            if token in seen or len(token) < 3:
                continue
            seen.add(token)
            terms.append(token)
            if len(terms) >= limit:
                break
        return terms

    def _shape(self, raw_message: dict[str, Any]) -> dict[str, Any]:
        """Transform a GPU inference result into a schema-compliant shaped packet."""
        content_id = str(uuid.uuid4())
        shape_id = str(uuid.uuid4())
        request_id = raw_message.get("request_id", "unknown")
        source_ref = f"{SUBSCRIBE_SUBJECT}/{request_id}"
        text = self._extract_text(raw_message)
        anchor_terms = self._extract_terms(text)
        semantic_weights = [{"term": term, "weight": 1.0} for term in anchor_terms]
        # Heuristic density: longer text → higher density, capped at 1.0.
        semantic_density = min(1.0, max(0.0, 0.1 + 0.05 * len(text.split())))

        shaped: dict[str, Any] = {
            "content_id": content_id,
            "text": text,
            "source_ref": source_ref,
            "content_type": raw_message.get("envelope_type") or "gpu.inference.result.v1",
            "shape_id": shape_id,
            "aliases": [],
            "favorite_words": [],
            "anchor_terms": anchor_terms,
            "semantic_weights": semantic_weights,
            "noise_score": 0.0,
            "semantic_density": semantic_density,
            "labels": [
                "spark",
                "gpu",
                str(raw_message.get("model_id", "unknown")),
            ],
            "meta": {
                "source_subject": SUBSCRIBE_SUBJECT,
                "source_node": str(raw_message.get("node_id") or raw_message.get("node", "unknown")),
                "source_model": str(raw_message.get("model_id", "unknown")),
                "request_id": request_id,
                "shaped_at": datetime.now(timezone.utc).isoformat(),
                "inference": {
                    "prompt_tokens": raw_message.get("prompt_tokens", 0),
                    "completion_tokens": raw_message.get("completion_tokens", 0),
                    "duration_ms": raw_message.get("duration_ms", 0),
                },
                "signature": "",
            },
        }
        shaped["meta"]["signature"] = self._attestation(shaped)
        return shaped

    @staticmethod
    def _validate_shaped(shaped: dict[str, Any]) -> bool:
        """Lightweight contract check for required lexicon.shaped.v1 fields."""
        required = {
            "content_id": str,
            "text": str,
            "source_ref": str,
            "shape_id": str,
            "anchor_terms": list,
            "semantic_weights": list,
            "noise_score": (int, float),
            "semantic_density": (int, float),
        }
        for key, expected in required.items():
            value = shaped.get(key)
            if value is None or not isinstance(value, expected):
                print(f"[shape-worker] shaped packet missing/invalid field: {key}", file=sys.stderr)
                return False
            if key in ("content_id", "text", "source_ref", "shape_id") and (not isinstance(value, str) or not value):
                print(f"[shape-worker] shaped packet empty required string: {key}", file=sys.stderr)
                return False
        for item in shaped["semantic_weights"]:
            if not isinstance(item, dict) or not isinstance(item.get("term"), str) or not isinstance(item.get("weight"), (int, float)):
                print("[shape-worker] invalid semantic_weights item", file=sys.stderr)
                return False
        for score in (shaped["noise_score"], shaped["semantic_density"]):
            if not 0 <= score <= 1:
                print(f"[shape-worker] score out of range: {score}", file=sys.stderr)
                return False
        return True

    def _handshake(self, shaped: dict[str, Any]) -> dict[str, Any]:
        """Build the shape-capsule envelope expected by mesh-agent/main.py."""
        sig = ""
        if self.mesh_passphrase:
            mac = hmac.new(
                self.mesh_passphrase.encode("utf-8"),
                self._canon(shaped),
                hashlib.sha256,
            ).digest()
            sig = base64.b64encode(mac).decode("ascii")
        return {
            "type": "shape-capsule",
            "capsule": {
                "kind": "cgp",
                "data": shaped,
                "sig": {"hmac": sig},
            },
        }

    async def _on_result(self, msg) -> None:
        try:
            raw = json.loads(msg.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"[shape-worker] dropping non-JSON message: {exc}", file=sys.stderr)
            return

        if not isinstance(raw, dict):
            print(f"[shape-worker] dropping non-object JSON message: {type(raw).__name__}", file=sys.stderr)
            return

        shaped = self._shape(raw)
        if not self._validate_shaped(shaped):
            return

        shaped_data = json.dumps(shaped, default=str).encode("utf-8")
        await self.nc.publish(PUBLISH_SHAPED, shaped_data)
        print(f"[shape-worker] emitted {PUBLISH_SHAPED} content_id={shaped['content_id']}")

        handshake = self._handshake(shaped)
        handshake_data = json.dumps(handshake, default=str).encode("utf-8")
        await self.nc.publish(PUBLISH_HANDSHAKE, handshake_data)
        print(f"[shape-worker] emitted {PUBLISH_HANDSHAKE} content_id={shaped['content_id']}")

    async def run(self) -> int:
        self.nc = await nats.connect(self.nats_url)
        self.sub = await self.nc.subscribe(SUBSCRIBE_SUBJECT, cb=self._on_result)
        print(f"[shape-worker] connected to {_redact_url(self.nats_url)}")
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
    worker = ShapeWorker(NATS_URL, SHAPE_SECRET, MESH_PASSPHRASE)
    return await worker.run()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
