"""PMOVES P7 room and session orchestrator.

P7 owns two related but distinct state machines:

* ``room.stage`` is the persistent room lifecycle:
  rehearsal -> live -> review -> archive.
* ``session.state`` is transient runtime state:
  planned -> active/paused -> ended -> archived.

Git remains the canonical room-manifest seed. Runtime transitions are recorded in
Supabase and emitted as versioned NATS facts; the service never rewrites manifests.
``p7.nats.launch`` and ``p7.nats.session`` are command subjects, while
``p7.room.*.v1`` subjects are emitted facts.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import httpx
import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_ssh_public_key
from fastapi import Depends, FastAPI, Header, HTTPException
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, Field

from pmoves.services.common.env import get_secret
from pmoves.services.common.events import validate_payload

LOG = logging.getLogger("p7-room-orchestrator")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def _default_pmoves_root() -> Path:
    """Locate PMOVES config in either the packaged image or source tree."""
    packaged_root = Path("/app/pmoves")
    if packaged_root.is_dir():
        return packaged_root
    source_file = Path(__file__).resolve()
    return source_file.parents[2] if len(source_file.parents) > 2 else source_file.parent


PMOVES_ROOT = Path(os.getenv("PMOVES_ROOT", str(_default_pmoves_root())))
ROOM_CATALOG_PATH = Path(
    os.getenv("ROOM_CATALOG_PATH", str(PMOVES_ROOT / "config" / "rooms" / "catalog.json"))
)
SIGNING_CARDS_PATH = Path(
    os.getenv(
        "SIGNING_CARDS_PATH",
        str(PMOVES_ROOT / "config" / "signing_identity_cards.yaml"),
    )
)
SIGNING_CARD_SCHEMA_PATH = Path(
    os.getenv(
        "SIGNING_CARD_SCHEMA_PATH",
        str(PMOVES_ROOT / "contracts" / "schemas" / "identity" / "signing-card.v1.schema.json"),
    )
)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_REST_URL = os.getenv(
    "P7_SUPABASE_REST_URL",
    f"{SUPABASE_URL}/rest/v1" if SUPABASE_URL else "",
).rstrip("/")
SUPABASE_KEY = get_secret("SUPABASE_SERVICE_ROLE_KEY", "") or ""
SUPABASE_SCHEMA = os.getenv("P7_SUPABASE_SCHEMA", "pmoves_core")
NATS_URL = os.getenv("NATS_URL", "")
P7_CONTROL_TOKEN = get_secret("P7_CONTROL_TOKEN", "") or ""
ACTIVATION_PROOF_MAX_AGE_SECONDS = int(os.getenv("P7_ACTIVATION_PROOF_MAX_AGE_SECONDS", "300"))
HYDRATION_ATTEMPTS = int(os.getenv("P7_HYDRATION_ATTEMPTS", "3"))
HYDRATION_RETRY_SECONDS = float(os.getenv("P7_HYDRATION_RETRY_SECONDS", "1"))

NATS_COMMAND_LAUNCH = "p7.nats.launch"
NATS_COMMAND_SESSION = "p7.nats.session"
NATS_COMMAND_LAUNCH_V1 = f"{NATS_COMMAND_LAUNCH}.v1"
NATS_COMMAND_SESSION_V1 = f"{NATS_COMMAND_SESSION}.v1"
NATS_SUBJECT_STARTED = "p7.room.session.started.v1"
NATS_SUBJECT_CHECKPOINT = "p7.room.checkpoint.v1"
NATS_SUBJECT_ENDED = "p7.room.session.ended.v1"
NATS_SUBJECT_STAGE = "p7.room.stage.changed.v1"
NATS_SUBJECT_FAILED = "p7.room.command.failed.v1"


class RoomStage(str, Enum):
    REHEARSAL = "rehearsal"
    LIVE = "live"
    REVIEW = "review"
    ARCHIVE = "archive"


class SessionState(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    ARCHIVED = "archived"


class ActivationProof(BaseModel):
    """Nonce-bound proof that the caller controls the selected signing card."""

    card_id: str
    nonce: str = Field(min_length=16, max_length=256)
    issued_at: int
    signature: str = Field(min_length=16, max_length=4096)


STAGE_TRANSITIONS: dict[RoomStage, list[RoomStage]] = {
    RoomStage.REHEARSAL: [RoomStage.LIVE],
    RoomStage.LIVE: [RoomStage.REVIEW],
    RoomStage.REVIEW: [RoomStage.LIVE, RoomStage.ARCHIVE],
    RoomStage.ARCHIVE: [],
}

SESSION_TRANSITIONS: dict[SessionState, list[SessionState]] = {
    SessionState.PLANNED: [SessionState.ACTIVE],
    SessionState.ACTIVE: [SessionState.PAUSED, SessionState.ENDED],
    SessionState.PAUSED: [SessionState.ACTIVE, SessionState.ENDED],
    SessionState.ENDED: [SessionState.ARCHIVED],
    SessionState.ARCHIVED: [],
}


class RoomSession:
    def __init__(self, room_id: str, manifest: dict[str, Any]):
        self.room_id = room_id
        self.manifest = manifest
        self.stage = RoomStage(manifest["stage"])
        self.state = SessionState.PLANNED
        self.session_id = str(uuid.uuid4())
        self.started_at: float | None = None
        self.ended_at: float | None = None
        self.checkpoints: list[dict[str, Any]] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "session_id": self.session_id,
            "stage": self.stage.value,
            "session_state": self.state.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "checkpoint_count": len(self.checkpoints),
            "manifest": self.manifest,
        }


_sessions: dict[str, RoomSession] = {}
_room_stages: dict[str, RoomStage] = {}
_room_locks: dict[str, asyncio.Lock] = {}
_used_activation_nonces: dict[str, float] = {}


def _iso_timestamp(value: float | None) -> str | None:
    """Convert an internal epoch timestamp to PostgREST-safe ISO 8601."""
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_catalog() -> dict[str, Any]:
    if not ROOM_CATALOG_PATH.exists():
        raise HTTPException(status_code=503, detail=f"Room catalog not found: {ROOM_CATALOG_PATH}")
    return _read_json(ROOM_CATALOG_PATH)


def get_room_manifest(room_id: str) -> dict[str, Any]:
    """Resolve and load the manifest referenced by a catalog entry."""
    entry = next(
        (room for room in load_catalog().get("rooms", []) if room.get("room_id") == room_id),
        None,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not in catalog")

    manifest_name = entry.get("manifest")
    if not manifest_name:
        raise HTTPException(status_code=500, detail=f"Room '{room_id}' has no manifest reference")

    room_dir = ROOM_CATALOG_PATH.parent.resolve()
    manifest_path = (room_dir / manifest_name).resolve()
    if manifest_path.parent != room_dir:
        raise HTTPException(status_code=500, detail=f"Unsafe manifest path for room '{room_id}'")
    if not manifest_path.is_file():
        raise HTTPException(status_code=500, detail=f"Manifest not found for room '{room_id}'")

    manifest = _read_json(manifest_path)
    if manifest.get("room_id") != room_id:
        raise HTTPException(status_code=500, detail=f"Manifest room_id mismatch for '{room_id}'")
    if manifest.get("stage") != entry.get("stage"):
        raise HTTPException(status_code=500, detail=f"Catalog stage mismatch for '{room_id}'")
    return manifest


def _load_signing_cards() -> list[dict[str, Any]]:
    if not SIGNING_CARDS_PATH.is_file() or not SIGNING_CARD_SCHEMA_PATH.is_file():
        raise HTTPException(status_code=503, detail="CHIT signing-card configuration unavailable")
    raw = yaml.safe_load(SIGNING_CARDS_PATH.read_text(encoding="utf-8")) or {}
    return raw.get("cards") or []


def _resolve_signing_card(manifest: dict[str, Any]) -> dict[str, Any]:
    """Resolve and validate the signing card authorized by a room manifest."""
    cards = _load_signing_cards()
    chit = (manifest.get("meta") or {}).get("chit") or {}
    card_id = chit.get("card_id")

    if card_id:
        card = next((item for item in cards if item.get("card_id") == card_id), None)
    else:
        card = next(
            (
                item
                for item in cards
                if (item.get("h") or {}).get("agent_id") == manifest.get("agent_id")
                and item.get("active") is True
            ),
            None,
        )
    if card is None:
        raise HTTPException(status_code=422, detail="CHIT validation failed: no active signing card")

    schema = _read_json(SIGNING_CARD_SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(card),
        key=lambda error: list(error.path),
    )
    if errors:
        raise HTTPException(
            status_code=422,
            detail=f"CHIT validation failed: signing card invalid ({errors[0].message})",
        )
    if card.get("active") is not True:
        raise HTTPException(status_code=422, detail="CHIT validation failed: signing card inactive")

    card_agent = (card.get("h") or {}).get("agent_id")
    allowed_agents = {manifest.get("agent_id")}
    if chit.get("interim") is True and chit.get("creator_id"):
        allowed_agents.add(chit["creator_id"])
    if card_agent not in allowed_agents:
        raise HTTPException(status_code=422, detail="CHIT validation failed: signing-card owner mismatch")
    return card


def _activation_message(
    room_id: str,
    session_id: str,
    previous_stage: RoomStage,
    target: RoomStage,
    proof: ActivationProof,
) -> bytes:
    """Build the canonical bytes signed for a live-stage activation."""
    return json.dumps(
        {
            "card_id": proof.card_id,
            "issued_at": proof.issued_at,
            "nonce": proof.nonce,
            "previous_stage": previous_stage.value,
            "room_id": room_id,
            "session_id": session_id,
            "target_stage": target.value,
            "version": "p7-room-activation-v1",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def validate_chit(
    manifest: dict[str, Any],
    proof: ActivationProof | None,
    message: bytes,
) -> str:
    """Verify card eligibility and nonce-bound SSH proof-of-possession."""
    card = _resolve_signing_card(manifest)
    if proof is None:
        raise HTTPException(status_code=401, detail="CHIT activation proof required")
    if proof.card_id != card["card_id"]:
        raise HTTPException(status_code=403, detail="CHIT activation proof card mismatch")

    now = time.time()
    if abs(now - proof.issued_at) > ACTIVATION_PROOF_MAX_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="CHIT activation proof expired")
    for nonce, expires_at in list(_used_activation_nonces.items()):
        if expires_at <= now:
            _used_activation_nonces.pop(nonce, None)
    if proof.nonce in _used_activation_nonces:
        raise HTTPException(status_code=409, detail="CHIT activation proof nonce already used")

    ml = card.get("ml") or {}
    if ml.get("primary_method") != "ssh" or not ml.get("ssh_allowed_signers_line"):
        raise HTTPException(
            status_code=422,
            detail="CHIT signing card has no locally verifiable SSH key material",
        )
    allowed_signer_parts = str(ml["ssh_allowed_signers_line"]).split()
    try:
        key_index = next(
            index
            for index, part in enumerate(allowed_signer_parts)
            if part.startswith(("ssh-", "ecdsa-", "sk-"))
        )
        public_key = load_ssh_public_key(
            f"{allowed_signer_parts[key_index]} {allowed_signer_parts[key_index + 1]}".encode()
        )
        if not isinstance(public_key, Ed25519PublicKey):
            raise ValueError("only Ed25519 activation keys are supported")
        signature = base64.b64decode(proof.signature, validate=True)
        public_key.verify(signature, message)
    except (InvalidSignature, ValueError, IndexError, StopIteration, binascii.Error) as exc:
        raise HTTPException(status_code=403, detail="CHIT activation proof invalid") from exc

    _used_activation_nonces[proof.nonce] = now + ACTIVATION_PROOF_MAX_AGE_SECONDS
    return card["card_id"]


async def record_session(session: RoomSession, action: str, *, required: bool = False) -> None:
    """Record runtime state; live activation requires durable audit persistence."""
    if not SUPABASE_REST_URL or not SUPABASE_KEY:
        if required:
            raise HTTPException(status_code=503, detail="Supabase audit persistence required for live stage")
        LOG.info("Supabase not configured; skipping %s for %s", action, session.room_id)
        return
    payload = {
        "session_id": session.session_id,
        "room_id": session.room_id,
        "agent_id": session.manifest.get("agent_id"),
        "state": session.state.value,
        "started_at": _iso_timestamp(session.started_at),
        "ended_at": _iso_timestamp(session.ended_at),
        "metadata": {
            "stage": session.stage.value,
            "action": action,
            "history": session.checkpoints,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{SUPABASE_REST_URL}/room_sessions?on_conflict=session_id",
                json=payload,
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Content-Profile": SUPABASE_SCHEMA,
                    "Accept-Profile": SUPABASE_SCHEMA,
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
            )
            response.raise_for_status()
    except Exception as exc:
        if required:
            raise HTTPException(status_code=502, detail="Supabase audit persistence failed") from exc
        LOG.warning("Supabase record failed (%s); continuing rehearsal session", exc)


async def _hydrate_room_stages_once() -> tuple[dict[str, RoomStage], dict[str, float]]:
    """Read one complete durable-stage snapshot from Supabase."""
    catalog_room_ids = {
        room["room_id"] for room in load_catalog().get("rooms", []) if room.get("room_id")
    }
    stages: dict[str, RoomStage] = {}
    nonces: dict[str, float] = {}
    async with httpx.AsyncClient(timeout=10) as client:
        for room_id in catalog_room_ids:
            response = await client.get(
                f"{SUPABASE_REST_URL}/room_sessions",
                params={
                    "select": "metadata",
                    "room_id": f"eq.{room_id}",
                    "order": "started_at.desc",
                    "limit": 1,
                },
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Accept-Profile": SUPABASE_SCHEMA,
                },
            )
            response.raise_for_status()
            rows = response.json()
            if not rows:
                continue
            metadata = rows[0].get("metadata") or {}
            stages[room_id] = RoomStage(metadata.get("stage"))
            for checkpoint in metadata.get("history") or []:
                nonce = checkpoint.get("activation_nonce")
                issued_at = checkpoint.get("activation_issued_at")
                if nonce and issued_at:
                    nonces[str(nonce)] = float(issued_at) + ACTIVATION_PROOF_MAX_AGE_SECONDS
    return stages, nonces


async def hydrate_room_stages() -> None:
    """Hydrate a complete durable snapshot; configured persistence fails closed."""
    if not SUPABASE_REST_URL:
        LOG.info("Supabase not configured; using Git room stages as runtime seeds")
        return
    if not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required when Supabase is configured")

    last_error: Exception | None = None
    for attempt in range(1, max(HYDRATION_ATTEMPTS, 1) + 1):
        try:
            stages, nonces = await _hydrate_room_stages_once()
            _room_stages.update(stages)
            _used_activation_nonces.update(nonces)
            LOG.info("Hydrated durable stages for %d rooms", len(stages))
            return
        except Exception as exc:
            last_error = exc
            LOG.error(
                "Supabase stage hydration attempt %d/%d failed (%s)",
                attempt,
                max(HYDRATION_ATTEMPTS, 1),
                exc,
            )
            if attempt < max(HYDRATION_ATTEMPTS, 1):
                await asyncio.sleep(HYDRATION_RETRY_SECONDS)
    raise RuntimeError("Supabase stage hydration failed; refusing Git-seed fallback") from last_error


class NATSPublisher:
    def __init__(self) -> None:
        self._nc: Any = None

    @property
    def connected(self) -> bool:
        return bool(self._nc and self._nc.is_connected)

    async def connect(self) -> None:
        if not NATS_URL:
            LOG.info("NATS_URL not configured; command subjects disabled")
            return
        try:
            from nats.aio.client import Client as NATSClient

            self._nc = NATSClient()
            await self._nc.connect(servers=[NATS_URL])
            for subject in (NATS_COMMAND_LAUNCH, NATS_COMMAND_LAUNCH_V1):
                await self._nc.subscribe(subject, cb=self._handle_launch)
            for subject in (NATS_COMMAND_SESSION, NATS_COMMAND_SESSION_V1):
                await self._nc.subscribe(subject, cb=self._handle_session)
            LOG.info("Connected to NATS and subscribed to P7 command subjects")
        except Exception as exc:
            LOG.warning("NATS connect failed (%s); HTTP control remains available", exc)
            self._nc = None

    async def publish(
        self,
        subject: str,
        payload: dict[str, Any],
        *,
        required: bool = False,
    ) -> None:
        validate_payload(subject, payload)
        body = json.dumps(payload).encode()
        if not self.connected:
            if required:
                raise HTTPException(status_code=503, detail=f"NATS fact delivery required: {subject}")
            LOG.warning("NATS disconnected; skipped fact subject=%s", subject)
            return
        try:
            await self._nc.publish(subject, body)
            if required:
                await self._nc.flush(timeout=5)
        except Exception as exc:
            if required:
                raise HTTPException(status_code=502, detail=f"NATS fact delivery failed: {subject}") from exc
            LOG.warning("NATS publish failed subject=%s (%s)", subject, exc)
            return
        LOG.info("NATS fact subject=%s bytes=%d", subject, len(body))

    async def close(self) -> None:
        if self._nc:
            await self._nc.drain()
            self._nc = None

    async def _fail_command(self, command: str, payload: dict[str, Any], exc: Exception) -> None:
        detail = getattr(exc, "detail", str(exc))
        await self.publish(
            NATS_SUBJECT_FAILED,
            {"command": command, "payload": payload, "detail": detail, "ts": time.time()},
        )

    async def _handle_launch(self, message: Any) -> None:
        payload: dict[str, Any] = {}
        try:
            payload = json.loads(message.data.decode())
            room_id = payload.get("room_id") or payload["room"]
            action = str(payload.get("action") or "start").lower()
            target = {
                "start": SessionState.ACTIVE,
                "started": SessionState.ACTIVE,
                "end": SessionState.ENDED,
                "stop": SessionState.ENDED,
                "stopped": SessionState.ENDED,
            }[action]
            await transition_session(
                room_id,
                target,
                rollover=action in {"start", "started"},
            )
        except Exception as exc:
            await self._fail_command(NATS_COMMAND_LAUNCH, payload, exc)

    async def _handle_session(self, message: Any) -> None:
        payload: dict[str, Any] = {}
        try:
            payload = json.loads(message.data.decode())
            room_id = payload.get("room_id") or payload["room"]
            action = payload["action"]
            if action == "stage":
                proof = ActivationProof.model_validate(payload["proof"]) if payload.get("proof") else None
                await transition_stage(room_id, RoomStage(payload["target"]), proof=proof)
            else:
                target = {
                    "start": SessionState.ACTIVE,
                    "started": SessionState.ACTIVE,
                    "pause": SessionState.PAUSED,
                    "resume": SessionState.ACTIVE,
                    "end": SessionState.ENDED,
                    "stop": SessionState.ENDED,
                    "stopped": SessionState.ENDED,
                    "archive": SessionState.ARCHIVED,
                }[action]
                await transition_session(
                    room_id,
                    target,
                    rollover=action in {"start", "started"},
                )
        except Exception as exc:
            await self._fail_command(NATS_COMMAND_SESSION, payload, exc)


publisher = NATSPublisher()


def get_or_create_session(room_id: str) -> RoomSession:
    session = _sessions.get(room_id)
    if session is None:
        session = RoomSession(room_id, get_room_manifest(room_id))
        session.stage = _room_stages.get(room_id, session.stage)
        _sessions[room_id] = session
    return session


async def transition_session(
    room_id: str,
    target: SessionState,
    *,
    rollover: bool = False,
) -> RoomSession:
    lock = _room_locks.setdefault(room_id, asyncio.Lock())
    async with lock:
        return await _transition_session(room_id, target, rollover=rollover)


async def _transition_session(
    room_id: str,
    target: SessionState,
    *,
    rollover: bool = False,
) -> RoomSession:
    session = get_or_create_session(room_id)
    if target == SessionState.ACTIVE and session.stage == RoomStage.ARCHIVE:
        raise HTTPException(status_code=409, detail="Archived room cannot start a new session")
    if rollover and target == SessionState.ACTIVE and session.state in {
        SessionState.ENDED,
        SessionState.ARCHIVED,
    }:
        replacement = RoomSession(room_id, get_room_manifest(room_id))
        replacement.stage = _room_stages.get(room_id, session.stage)
        _sessions[room_id] = replacement
        session = replacement
    current = session.state
    if target not in SESSION_TRANSITIONS[current]:
        raise HTTPException(status_code=409, detail=f"Invalid session transition: {current.value} -> {target.value}")

    session.state = target
    now = time.time()
    if target == SessionState.ACTIVE and session.started_at is None:
        session.started_at = now
    elif target == SessionState.ENDED and session.ended_at is None:
        session.ended_at = now
    session.checkpoints.append(
        {
            "session_state": target.value,
            "previous_session_state": current.value,
            "stage": session.stage.value,
            "ts": now,
        }
    )
    await record_session(session, f"session:{current.value}->{target.value}")

    subject = None
    if current == SessionState.PLANNED and target == SessionState.ACTIVE:
        subject = NATS_SUBJECT_STARTED
    elif target == SessionState.ENDED:
        subject = NATS_SUBJECT_ENDED
    if subject:
        await publisher.publish(subject, session.to_dict())
    await publisher.publish(NATS_SUBJECT_CHECKPOINT, session.to_dict())
    return session


async def transition_stage(
    room_id: str,
    target: RoomStage,
    *,
    proof: ActivationProof | None = None,
) -> RoomSession:
    lock = _room_locks.setdefault(room_id, asyncio.Lock())
    async with lock:
        return await _transition_stage(room_id, target, proof=proof)


async def _transition_stage(
    room_id: str,
    target: RoomStage,
    *,
    proof: ActivationProof | None = None,
) -> RoomSession:
    session = get_or_create_session(room_id)
    current = session.stage
    if target not in STAGE_TRANSITIONS[current]:
        raise HTTPException(status_code=409, detail=f"Invalid stage transition: {current.value} -> {target.value}")

    if target == RoomStage.LIVE and session.state != SessionState.ACTIVE:
        raise HTTPException(status_code=409, detail="Room session must be active before stage can transition to live")
    if target == RoomStage.ARCHIVE and session.state not in {
        SessionState.ENDED,
        SessionState.ARCHIVED,
    }:
        raise HTTPException(status_code=409, detail="Room session must be ended before room can transition to archive")

    if not publisher.connected:
        raise HTTPException(status_code=503, detail="NATS stage-fact delivery required for stage transition")

    card_id = None
    if target == RoomStage.LIVE:
        activation_message = _activation_message(
            room_id,
            session.session_id,
            current,
            target,
            proof,
        ) if proof is not None else b""
        card_id = validate_chit(session.manifest, proof, activation_message)

    previous = session.stage
    session.stage = target
    now = time.time()
    session.checkpoints.append(
        {
            "session_state": session.state.value,
            "stage": target.value,
            "previous_stage": previous.value,
            "signing_card_id": card_id,
            "activation_nonce": proof.nonce if proof else None,
            "activation_issued_at": proof.issued_at if proof else None,
            "ts": now,
        }
    )
    try:
        await record_session(
            session,
            f"stage:{previous.value}->{target.value}",
            required=True,
        )
    except Exception:
        session.stage = previous
        session.checkpoints.pop()
        raise

    payload = session.to_dict()
    payload.update({"previous_stage": previous.value, "signing_card_id": card_id, "ts": now})
    try:
        await publisher.publish(
            NATS_SUBJECT_STAGE,
            payload,
            required=True,
        )
    except Exception as publish_exc:
        session.stage = previous
        session.checkpoints.append(
            {
                "session_state": session.state.value,
                "stage": previous.value,
                "previous_stage": target.value,
                "failed_stage": target.value,
                "signing_card_id": card_id,
                "error": str(getattr(publish_exc, "detail", publish_exc)),
                "rollback": True,
                "ts": time.time(),
            }
        )
        try:
            await record_session(
                session,
                f"stage-rollback:{target.value}->{previous.value}",
                required=True,
            )
        except Exception as rollback_exc:
            raise HTTPException(
                status_code=502,
                detail="NATS stage fact failed and Supabase stage rollback failed",
            ) from rollback_exc
        raise publish_exc
    _room_stages[room_id] = target
    return session


class StageRequest(BaseModel):
    target: RoomStage
    proof: ActivationProof | None = None


def require_http_control(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Authenticate HTTP control-plane mutations with a secret-aware bearer token."""
    if not P7_CONTROL_TOKEN:
        raise HTTPException(status_code=503, detail="P7 HTTP control token not configured")
    scheme, _, credential = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(credential, P7_CONTROL_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid P7 HTTP control credentials")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await hydrate_room_stages()
    await publisher.connect()
    yield
    await publisher.close()


app = FastAPI(title="PMOVES P7 Room Orchestrator", version="1.2.0", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    catalog = load_catalog()
    return {
        "status": "ok",
        "rooms_in_catalog": len(catalog.get("rooms", [])),
        "sessions": len(_sessions),
        "nats_connected": publisher.connected,
    }


@app.get("/api/v1/rooms/{room_id}")
async def get_room(room_id: str) -> dict[str, Any]:
    return get_or_create_session(room_id).to_dict()


@app.post("/api/v1/rooms/{room_id}/start")
async def start_room(
    room_id: str,
    _: Annotated[None, Depends(require_http_control)],
) -> dict[str, Any]:
    return (await transition_session(room_id, SessionState.ACTIVE, rollover=True)).to_dict()


@app.post("/api/v1/rooms/{room_id}/pause")
async def pause_room(
    room_id: str,
    _: Annotated[None, Depends(require_http_control)],
) -> dict[str, Any]:
    return (await transition_session(room_id, SessionState.PAUSED)).to_dict()


@app.post("/api/v1/rooms/{room_id}/resume")
async def resume_room(
    room_id: str,
    _: Annotated[None, Depends(require_http_control)],
) -> dict[str, Any]:
    return (await transition_session(room_id, SessionState.ACTIVE)).to_dict()


@app.post("/api/v1/rooms/{room_id}/end")
async def end_room(
    room_id: str,
    _: Annotated[None, Depends(require_http_control)],
) -> dict[str, Any]:
    return (await transition_session(room_id, SessionState.ENDED)).to_dict()


@app.post("/api/v1/rooms/{room_id}/archive-session")
async def archive_session(
    room_id: str,
    _: Annotated[None, Depends(require_http_control)],
) -> dict[str, Any]:
    return (await transition_session(room_id, SessionState.ARCHIVED)).to_dict()


@app.post("/api/v1/rooms/{room_id}/stage")
async def set_room_stage(
    room_id: str,
    request: StageRequest,
    _: Annotated[None, Depends(require_http_control)],
) -> dict[str, Any]:
    return (await transition_stage(room_id, request.target, proof=request.proof)).to_dict()


@app.get("/api/v1/rooms")
async def list_rooms() -> dict[str, Any]:
    rooms = []
    for entry in load_catalog().get("rooms", []):
        room_id = entry["room_id"]
        session = _sessions.get(room_id)
        rooms.append(
            {
                "room_id": room_id,
                "display_name": entry.get("display_name", ""),
                "stage": (
                    session.stage.value
                    if session
                    else _room_stages.get(room_id, RoomStage(entry["stage"])).value
                ),
                "session_state": session.state.value if session else "uninitialized",
                "session_id": session.session_id if session else None,
            }
        )
    return {"rooms": rooms, "total": len(rooms)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8122")))
