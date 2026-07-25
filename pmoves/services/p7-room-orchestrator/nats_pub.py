"""
P7 NATS Publisher
=================

Publishes room-lifecycle events on the P7 control plane subjects:

  p7.nats.launch                    room entered
  p7.nats.session                   room session opened/closed
  room.session.updated.v1           stage changed (also declared in room manifest telemetry)
  pmoves.config.rooms.reloaded.v1   catalog reloaded

Every payload is wrapped with a `chit` block containing the P7 service's
signing card id, an HMAC-SHA256 signature, and a UTC timestamp. When
P7_SERVICE_CARD_ID is unset (e.g. local dev), payloads are published with
`status: unsigned-local` advisory and the signature is an empty string —
this is the same fail-soft convention the rest of PMOVES uses for
session-end provenance (per BOOTSTRAP.md).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

LOG = logging.getLogger("p7.nats")


# ---- Subject constants (per p7-service-spec-2026-07-20.md §6) ----
SUBJECT_LAUNCH = "p7.nats.launch"
SUBJECT_SESSION = "p7.nats.session"
SUBJECT_ROOM_UPDATED = "room.session.updated.v1"
SUBJECT_CONFIG_RELOADED = "pmoves.config.rooms.reloaded.v1"


class NATSPublisher:
    """
    Async NATS publisher for the P7 control plane.

    Connection is established lazily on first publish. On connect failure,
    publishes fall back to log-only mode (`NATS_AVAILABLE = False`) so the
    service still serves HTTP transitions; the local catalog is the source
    of truth and NATS is the fanout.
    """

    def __init__(self, nats_url: str, service_card_id: str = "",
                 connect_timeout_sec: int = 10,
                 retry_max_attempts: int = 5,
                 retry_backoff_sec: float = 1.5,
                 signing_key: str = ""):
        self._nats_url = nats_url
        self._service_card_id = service_card_id
        self._connect_timeout = connect_timeout_sec
        self._retry_max = retry_max_attempts
        self._retry_backoff = retry_backoff_sec
        self._signing_key = signing_key  # if set, use HMAC; else unsigned-local
        self._nc = None
        self._lock = asyncio.Lock()
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        """Connect to NATS. Returns True on success, False on failure (log-only mode).

        This is the one-shot lazy-connect path used when `publish()` discovers
        we're not connected. For the lifespan (startup) path, use
        `connect_with_retry()` so we respect `retry_max_attempts` +
        `retry_backoff_sec`.
        """
        async with self._lock:
            if self._connected:
                return True
            try:
                from nats.aio.client import Client as NATSClient
                # Drain any stale client (e.g. a mid-stream publish failure set
                # _connected=False) before replacing it, so we don't leak the
                # old connection when reconnecting.
                if self._nc is not None:
                    try:
                        await self._nc.drain()
                    except Exception:
                        pass
                    self._nc = None
                self._nc = NATSClient()
                await asyncio.wait_for(
                    self._nc.connect(servers=[self._nats_url]),
                    timeout=self._connect_timeout,
                )
                self._connected = True
                LOG.info("NATS connected at %s", self._nats_url)
                return True
            except Exception as exc:
                LOG.warning("NATS connect failed (%s); running log-only", exc)
                self._nc = None
                self._connected = False
                return False

    async def connect_with_retry(self) -> bool:
        """Connect to NATS with bounded retry + exponential backoff.

        Up to `retry_max_attempts` attempts; between attempts, sleep
        `retry_backoff_sec * 2**attempt` (capped at 60s) so we don't hammer
        a slow NATS server during cold start. The total wait time is bounded
        by sum(backoff[0..max_attempts-1]).

        Returns True on first successful connect, False if all attempts fail
        (caller should treat as log-only mode).
        """
        last_exc: Optional[BaseException] = None
        for attempt in range(self._retry_max):
            try:
                ok = await self.connect()
                if ok:
                    if attempt > 0:
                        LOG.info("NATS connect succeeded on attempt %d/%d",
                                 attempt + 1, self._retry_max)
                    return True
                last_exc = RuntimeError("connect() returned False")
            except Exception as exc:  # defensive — connect() should not raise
                last_exc = exc
            # Don't sleep after the final attempt.
            if attempt < self._retry_max - 1:
                backoff = min(self._retry_backoff * (2 ** attempt), 60.0)
                LOG.warning(
                    "NATS connect attempt %d/%d failed (%s); retrying in %.1fs",
                    attempt + 1, self._retry_max, last_exc, backoff,
                )
                await asyncio.sleep(backoff)
        LOG.error(
            "NATS connect gave up after %d attempts (last error: %s); log-only mode",
            self._retry_max, last_exc,
        )
        return False

    async def disconnect(self) -> None:
        async with self._lock:
            if self._nc is not None and self._connected:
                try:
                    await self._nc.drain()
                except Exception:
                    pass
            self._connected = False
            self._nc = None

    def _sign(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrap payload with a `chit` block (signing card id + signature + ts).

        If P7 has no signing key configured, emits `status: unsigned-local`
        per the same convention used in BOOTSTRAP.md and the rest of PMOVES.
        """
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        chit_block: Dict[str, Any] = {
            "kid": self._service_card_id or None,
            "ts": _utcnow_iso(),
            "status": "signed" if self._signing_key and self._service_card_id else "unsigned-local",
            "signature": "",
        }
        if chit_block["status"] == "signed":
            mac = hmac.new(
                self._signing_key.encode("utf-8"),
                body,
                hashlib.sha256,
            )
            chit_block["signature"] = mac.hexdigest()
        return {**payload, "chit": chit_block}

    async def publish(self, subject: str, payload: Dict[str, Any]) -> bool:
        """
        Sign payload, publish on NATS. Returns True if published (or queued),
        False if NATS unavailable AND log-only fallback failed.
        """
        signed = self._sign(payload)
        body = json.dumps(signed).encode("utf-8")
        if not self._connected:
            await self.connect()
        if self._connected and self._nc is not None:
            try:
                await self._nc.publish(subject, body)
                LOG.info("NATS publish subject=%s bytes=%d status=%s",
                         subject, len(body), signed["chit"]["status"])
                return True
            except Exception as exc:
                LOG.warning("NATS publish failed on %s (%s); falling back to log", subject, exc)
                self._connected = False
        # log-only fallback
        LOG.info("NATS-LOG subject=%s payload=%s", subject, signed)
        return True

    # ---- High-level helpers (semantic-named wrappers per spec §6) ----

    async def publish_room_launched(self, room_id: str, agent_id: str, alter: str,
                                    overlay: str, manifest_version: str) -> bool:
        return await self.publish(SUBJECT_LAUNCH, {
            "v": "1.0.0",
            "room_id": room_id,
            "agent_id": agent_id,
            "alter": alter,
            "overlay": overlay,
            "manifest_version": manifest_version,
            "timestamp": _utcnow_iso(),
        })

    async def publish_room_session(self, room_id: str, session_id: str,
                                  action: str, agent_id: str) -> bool:
        return await self.publish(SUBJECT_SESSION, {
            "v": "1.0.0",
            "room_id": room_id,
            "session_id": session_id,
            "action": action,  # "open" | "close" | "heartbeat"
            "agent_id": agent_id,
            "timestamp": _utcnow_iso(),
        })

    async def publish_room_updated(self, room_id: str, previous_stage: str,
                                   new_stage: str, reason: str, requester: str) -> bool:
        return await self.publish(SUBJECT_ROOM_UPDATED, {
            "v": "1.0.0",
            "room_id": room_id,
            "previous_stage": previous_stage,
            "new_stage": new_stage,
            "reason": reason,
            "requester": requester,
            "timestamp": _utcnow_iso(),
        })

    async def publish_config_reloaded(self, schema_version: str, rooms_loaded: int) -> bool:
        return await self.publish(SUBJECT_CONFIG_RELOADED, {
            "v": "1.0.0",
            "schema_version": schema_version,
            "rooms_loaded": rooms_loaded,
            "timestamp": _utcnow_iso(),
        })


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
