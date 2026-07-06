"""
PMOVES P7 Room Orchestrator Service
===================================
Manages room lifecycle with a state machine, CHIT validation on activation,
Supabase session recording, and NATS event publishing.

State machine:
    planned → active → (paused ↔ active)* → ended → archived

Endpoints:
    GET    /healthz
    POST   /api/v1/rooms/{room_id}/start
    POST   /api/v1/rooms/{room_id}/pause
    POST   /api/v1/rooms/{room_id}/resume
    POST   /api/v1/rooms/{room_id}/end
    GET    /api/v1/rooms
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

LOG = logging.getLogger("p7-room-orchestrator")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

ROOM_CATALOG_PATH = Path(os.getenv("ROOM_CATALOG_PATH", "pmoves/config/rooms/catalog.json"))
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
NATS_SUBJECT_STARTED = "p7.room.session.started.v1"
NATS_SUBJECT_CHECKPOINT = "p7.room.checkpoint.v1"
NATS_SUBJECT_ENDED = "p7.room.session.ended.v1"

# --------------------------------------------------------------------------- #
# State machine
# --------------------------------------------------------------------------- #

class RoomState(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    ARCHIVED = "archived"


TRANSITIONS: Dict[RoomState, List[RoomState]] = {
    RoomState.PLANNED: [RoomState.ACTIVE],
    RoomState.ACTIVE: [RoomState.PAUSED, RoomState.ENDED],
    RoomState.PAUSED: [RoomState.ACTIVE, RoomState.ENDED],
    RoomState.ENDED: [RoomState.ARCHIVED],
    RoomState.ARCHIVED: [],
}

# --------------------------------------------------------------------------- #
# In-memory session store (production: Supabase)
# --------------------------------------------------------------------------- #

class RoomSession:
    def __init__(self, room_id: str, manifest: Dict[str, Any]):
        self.room_id = room_id
        self.manifest = manifest
        self.state: RoomState = RoomState.PLANNED
        self.session_id: str = str(uuid.uuid4())
        self.started_at: Optional[float] = None
        self.ended_at: Optional[float] = None
        self.checkpoints: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "room_id": self.room_id,
            "session_id": self.session_id,
            "state": self.state.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "checkpoint_count": len(self.checkpoints),
            "manifest": self.manifest,
        }


_sessions: Dict[str, RoomSession] = {}


# --------------------------------------------------------------------------- #
# Room catalog loader
# --------------------------------------------------------------------------- #

def load_catalog() -> Dict[str, Any]:
    """Load room manifest catalog from disk."""
    if not ROOM_CATALOG_PATH.exists():
        LOG.warning("Room catalog not found at %s; returning empty catalog", ROOM_CATALOG_PATH)
        return {"rooms": []}
    data = json.loads(ROOM_CATALOG_PATH.read_text())
    return data


def get_room_manifest(room_id: str) -> Dict[str, Any]:
    catalog = load_catalog()
    for room in catalog.get("rooms", []):
        if room.get("room_id") == room_id or room.get("id") == room_id:
            return room
    raise HTTPException(status_code=404, detail=f"Room '{room_id}' not in catalog")


# --------------------------------------------------------------------------- #
# CHIT validation
# --------------------------------------------------------------------------- #

def validate_chit(manifest: Dict[str, Any]) -> None:
    """
    Validate CHIT (Capability, Handler, Integration, Trigger) prerequisites
    before transitioning from planned → active.
    """
    chit = manifest.get("chit") or {}
    missing = []
    for field in ("capability", "handler", "integration", "trigger"):
        if not chit.get(field):
            missing.append(field)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"CHIT validation failed for room: missing fields {missing}",
        )


# --------------------------------------------------------------------------- #
# Supabase recorder
# --------------------------------------------------------------------------- #

async def record_session(session: RoomSession, action: str) -> None:
    """Record session state to Supabase room_sessions table (best-effort)."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        LOG.info("Supabase not configured; skipping record for %s", session.room_id)
        return
    try:
        payload = {
            "session_id": session.session_id,
            "room_id": session.room_id,
            "state": session.state.value,
            "action": action,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/room_sessions",
                json=payload,
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
            )
            resp.raise_for_status()
        LOG.info("Recorded %s for room %s to Supabase", action, session.room_id)
    except Exception as exc:
        LOG.warning("Supabase record failed (%s); continuing", exc)


# --------------------------------------------------------------------------- #
# NATS publisher
# --------------------------------------------------------------------------- #

class NATSPublisher:
    def __init__(self):
        self._nc = None

    async def connect(self):
        try:
            from nats.aio.client import Client as NATSClient
            self._nc = NATSClient()
            await self._nc.connect(servers=[NATS_URL])
            LOG.info("Connected to NATS at %s", NATS_URL)
        except Exception as exc:
            LOG.warning("NATS connect failed (%s); events logged only", exc)
            self._nc = None

    async def publish(self, subject: str, payload: Dict[str, Any]):
        body = json.dumps(payload).encode()
        if self._nc:
            await self._nc.publish(subject, body)
        LOG.info("NATS publish subject=%s bytes=%d", subject, len(body))


publisher = NATSPublisher()


# --------------------------------------------------------------------------- #
# Transition engine
# --------------------------------------------------------------------------- #

async def transition(room_id: str, target: RoomState, publish_subject: Optional[str] = None) -> RoomSession:
    session = _sessions.get(room_id)
    if session is None:
        manifest = get_room_manifest(room_id)
        session = RoomSession(room_id, manifest)
        _sessions[room_id] = session

    current = session.state
    if target not in TRANSITIONS.get(current, []):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid transition: {current.value} → {target.value}",
        )

    # CHIT validation on planned → active
    if current == RoomState.PLANNED and target == RoomState.ACTIVE:
        validate_chit(session.manifest)

    session.state = target
    now = time.time()

    if target == RoomState.ACTIVE and session.started_at is None:
        session.started_at = now
    elif target == RoomState.ENDED and session.ended_at is None:
        session.ended_at = now

    session.checkpoints.append({"state": target.value, "ts": now})
    await record_session(session, f"transition:{current.value}->{target.value}")

    if publish_subject:
        await publisher.publish(publish_subject, {
            "room_id": room_id,
            "session_id": session.session_id,
            "state": target.value,
            "ts": now,
        })

    # Always send a checkpoint
    await publisher.publish(NATS_SUBJECT_CHECKPOINT, {
        "room_id": room_id,
        "session_id": session.session_id,
        "checkpoint_state": target.value,
        "ts": now,
    })

    return session


# --------------------------------------------------------------------------- #
# API models
# --------------------------------------------------------------------------- #

class StartRequest(BaseModel):
    chit_override: Optional[Dict[str, Any]] = Field(None, description="Override CHIT fields for activation")


# --------------------------------------------------------------------------- #
# FastAPI app
# --------------------------------------------------------------------------- #

app = FastAPI(title="PMOVES P7 Room Orchestrator", version="1.0.0")


@app.on_event("startup")
async def _startup():
    await publisher.connect()


@app.get("/healthz")
async def healthz():
    catalog = load_catalog()
    return {"status": "ok", "rooms_in_catalog": len(catalog.get("rooms", []))}


@app.post("/api/v1/rooms/{room_id}/start")
async def start_room(room_id: str, req: Optional[StartRequest] = None):
    manifest = get_room_manifest(room_id)
    if req and req.chit_override:
        manifest.setdefault("chit", {}).update(req.chit_override)
    if room_id not in _sessions:
        _sessions[room_id] = RoomSession(room_id, manifest)
    session = await transition(room_id, RoomState.ACTIVE, NATS_SUBJECT_STARTED)
    return session.to_dict()


@app.post("/api/v1/rooms/{room_id}/pause")
async def pause_room(room_id: str):
    session = await transition(room_id, RoomState.PAUSED)
    return session.to_dict()


@app.post("/api/v1/rooms/{room_id}/resume")
async def resume_room(room_id: str):
    session = await transition(room_id, RoomState.ACTIVE)
    return session.to_dict()


@app.post("/api/v1/rooms/{room_id}/end")
async def end_room(room_id: str):
    session = await transition(room_id, RoomState.ENDED, NATS_SUBJECT_ENDED)
    return session.to_dict()


@app.get("/api/v1/rooms")
async def list_rooms():
    catalog = load_catalog()
    rooms = []
    for room in catalog.get("rooms", []):
        rid = room.get("room_id") or room.get("id")
        sess = _sessions.get(rid)
        rooms.append({
            "room_id": rid,
            "name": room.get("name", ""),
            "state": sess.state.value if sess else "uninitialized",
            "session_id": sess.session_id if sess else None,
        })
    return {"rooms": rooms, "total": len(rooms)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8092)
