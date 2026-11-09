"""
P7 Room-Aware Stage Manager — FastAPI App
=========================================

Public HTTP API for room lifecycle management. Endpoints follow the spec at
`pmoves/docs/specs/p7-service-spec-2026-07-20.md`.

  GET  /healthz                                       service + catalog health
  GET  /api/p7/rooms                                  list rooms (catalog rows)
  GET  /api/p7/rooms/{room_id}                        room detail (manifest + stage)
  POST /api/p7/rooms/{room_id}/session                open/close room session (OpenRoom adapter)
  POST /api/p7/rooms/{room_id}/transition             state-machine transition
  POST /api/p7/reload                                 force re-read of catalog from disk

Default port: 8120. Set P7_HTTP_PORT to override.

Packaging note: this directory is named `p7-room-orchestrator` (kebab) but
Python imports require `p7_room_orchestrator` (snake). We use absolute
imports (not relative) so the modules work both as a script (Dockerfile
WORKDIR=/app + `uvicorn main:app`) and via `python -m`. The tests'
conftest.py adds this directory to sys.path so pytest can find the modules
without package init.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure this directory is on sys.path so absolute imports work whether the
# service is run as `uvicorn main:app` from the service dir OR as a module
# from elsewhere. Idempotent.
_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from fastapi import Depends, FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Shared secret-aware env helper (P7_CONTROL_TOKEN, P7_SIGNING_KEY, etc.)
# Walk upward for services/common instead of a fixed parents[3]: in the
# container the module lives at /app/main.py (two path components), so
# parents[3] raises IndexError before the ImportError fallback can engage
# (crash-loop observed at first bring-up, 2026-07-25).
import sys as _sys
for _cand in Path(__file__).resolve().parents:
    _common = _cand / "services" / "common"
    if _common.is_dir():
        if str(_common) not in _sys.path:
            # APPEND, never insert(0): services/common also ships config.py,
            # which would shadow this service's own `config` module and break
            # `from config import P7Settings` (relative-import ImportError).
            _sys.path.append(str(_common))
        break
try:
    from env import get_secret as _get_secret  # type: ignore
except ImportError:  # pragma: no cover
    def _get_secret(key: str, default: str | None = None) -> str | None:
        # Container fallback (services/common is not baked into the image).
        # Must honor the <KEY>_FILE convention — compose delivers
        # P7_SIGNING_KEY_FILE, which a plain os.environ lookup would
        # silently ignore, leaving the signing key unloaded in-container.
        import os
        file_path = os.environ.get(f"{key}_FILE")
        if file_path:
            try:
                with open(file_path, encoding="utf-8") as fh:
                    value = fh.read().strip()
                if value:
                    return value
            except OSError:
                pass
        return os.environ.get(key, default)

import hmac

from catalog import CatalogError, CatalogLoader, ManifestError
from config import P7Settings
from nats_pub import NATSPublisher
from transition import (
    ChecklistError,
    InvalidTransitionError,
    TransitionEngine,
    TransitionError,
)


LOG = logging.getLogger("p7.main")


# --------------------------------------------------------------------------- #
# Settings + shared resources (populated in lifespan)
# --------------------------------------------------------------------------- #

def _build_settings() -> P7Settings:
    s = P7Settings()
    logging.basicConfig(
        level=getattr(logging, s.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return s


SETTINGS: P7Settings = _build_settings()
CATALOG: Optional[CatalogLoader] = None
PUBLISHER: Optional[NATSPublisher] = None
ENGINE: Optional[TransitionEngine] = None

# P7 HTTP control token. Reads from P7_CONTROL_TOKEN or P7_CONTROL_TOKEN_FILE
# (secret-aware). When unset, mutating endpoints return 503 (fail-closed)
# rather than silently allow unauthenticated state changes.
P7_CONTROL_TOKEN: str = _get_secret("P7_CONTROL_TOKEN", "") or ""


def require_http_control(
    authorization: Optional[str] = Header(default=None),
) -> None:
    """Authenticate HTTP control-plane mutations with a secret-aware bearer token.

    Mirrors the original p7-room-orchestrator contract (see origin/main
    pmoves/services/p7-room-orchestrator/app.py). Returns:
      - 503 if the service is not configured with a token (fail-closed)
      - 401 if the request lacks a valid bearer credential
    """
    if not P7_CONTROL_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="P7 HTTP control token not configured (set P7_CONTROL_TOKEN or P7_CONTROL_TOKEN_FILE)",
        )
    scheme, _, credential = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(credential, P7_CONTROL_TOKEN):
        raise HTTPException(
            status_code=401, detail="Invalid P7 HTTP control credentials"
        )


# --------------------------------------------------------------------------- #
# Lifespan
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize catalog, NATS publisher, and transition engine on startup."""
    global CATALOG, PUBLISHER, ENGINE

    CATALOG = CatalogLoader(SETTINGS)
    # P7_SIGNING_KEY is secret-aware: prefer P7_SIGNING_KEY_FILE if the
    # operator mounted a key in a file (Docker secrets / k8s secret). This
    # mirrors the P7_CONTROL_TOKEN pattern above and aligns with the
    # `get_secret` helper at pmoves/services/common/env.py.
    signing_key = _get_secret("P7_SIGNING_KEY", "") or ""
    PUBLISHER = NATSPublisher(
        nats_url=SETTINGS.nats_url,
        service_card_id=SETTINGS.service_card_id,
        connect_timeout_sec=SETTINGS.nats_connect_timeout_sec,
        retry_max_attempts=SETTINGS.nats_retry_max_attempts,
        retry_backoff_sec=SETTINGS.nats_retry_backoff_sec,
        signing_key=signing_key,
    )
    # Startup connect with bounded retry + exponential backoff so the
    # service can wait out a slow NATS at boot. Falls back to log-only
    # mode if all attempts fail.
    await PUBLISHER.connect_with_retry()
    ENGINE = TransitionEngine(SETTINGS, CATALOG, PUBLISHER)

    # publish initial config-reloaded event
    cat = CATALOG.catalog()
    await PUBLISHER.publish_config_reloaded(
        schema_version=cat.get("schema_version", "?"),
        rooms_loaded=len(cat.get("rooms", [])),
    )
    LOG.info("P7 service ready (port=%d, catalog_rooms=%d)",
             SETTINGS.http_port, len(cat.get("rooms", [])))

    try:
        yield
    finally:
        if PUBLISHER is not None:
            await PUBLISHER.disconnect()


app = FastAPI(
    title="PMOVES P7 Room-Aware Stage Manager",
    version="1.0.0",
    description="Manages room lifecycle (rehearsal → live → review → archive) "
                "with CHIT activation gating on rehearsal→live, atomic catalog "
                "writeback, and signed NATS control-plane events.",
    lifespan=lifespan,
)


# --------------------------------------------------------------------------- #
# Exception handlers
# --------------------------------------------------------------------------- #

@app.exception_handler(ManifestError)
async def _manifest_error_handler(_: Request, exc: ManifestError) -> JSONResponse:
    return JSONResponse(
        status_code=404 if "not in catalog" in str(exc) else 422,
        content={"error": "manifest_error", "detail": str(exc)},
    )


@app.exception_handler(InvalidTransitionError)
async def _invalid_transition_handler(_: Request, exc: InvalidTransitionError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "invalid_transition", "detail": str(exc), **exc.details},
    )


@app.exception_handler(ChecklistError)
async def _checklist_error_handler(_: Request, exc: ChecklistError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "chit_checklist_failed", "detail": str(exc), **exc.details},
    )


@app.exception_handler(TransitionError)
async def _transition_error_handler(_: Request, exc: TransitionError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "transition_error", "detail": str(exc), **exc.details},
    )


@app.exception_handler(CatalogError)
async def _catalog_error_handler(_: Request, exc: CatalogError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": "catalog_error", "detail": str(exc)},
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fail-closed handler for any unhandled exception.

    The full exception (including stack trace) is logged server-side so
    operators can diagnose, but only a generic message is returned to the
    client to avoid leaking internals (paths, env values, library versions).
    Per CodeQL guidance for information-exposure findings.
    """
    LOG.exception("unhandled exception in %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": "an internal error occurred"},
    )


# --------------------------------------------------------------------------- #
# Pydantic models
# --------------------------------------------------------------------------- #

class TransitionRequest(BaseModel):
    target_stage: str = Field(..., description="One of: rehearsal, live, review, archive")
    reason: str = Field(..., min_length=1, description="Operator-supplied reason (audit trail)")
    requester: str = Field(..., min_length=1, description="Agent or operator id requesting the transition")


class SessionRequest(BaseModel):
    """Open/close a room session — called by the OpenRoom desktop adapter
    (pmovesRoomAdapter.ts) on room enter (action=open) and room leave
    (action=close). Best-effort: any failure logs but doesn't block the
    desktop. Returns a session_id the client can correlate in logs.
    """
    action: str = Field(..., description="One of: open, close")
    agent_id: str = Field(default="anonymous", description="Agent id (window.PMOVES_AGENT_ID)")
    alter: str = Field(default="", description="Agent alter (window.PMOVES_ALTER)")
    room_stage: str = Field(default="rehearsal", description="Room stage at session time (rehearsal/live/review/archive)")
    timestamp: str = Field(default="", description="Client-supplied ISO-8601 timestamp (advisory only)")


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    if CATALOG is None or PUBLISHER is None:
        return {"status": "starting", "rooms_loaded": 0, "nats_connected": False}
    cat = CATALOG.catalog()
    return {
        "status": "ok",
        "rooms_loaded": len(cat.get("rooms", [])),
        "schema_version": cat.get("schema_version", "?"),
        "nats_connected": PUBLISHER.connected,
        "service_card_id": SETTINGS.service_card_id or None,
        "chit_require_signature": SETTINGS.chit_require_signature,
    }


@app.get("/api/p7/rooms")
async def list_rooms() -> Dict[str, Any]:
    if CATALOG is None:
        raise HTTPException(status_code=503, detail="catalog not initialized")
    rooms = CATALOG.list_rooms()
    return {
        "schema_version": CATALOG.catalog().get("schema_version", "?"),
        "rooms": rooms,
        "total": len(rooms),
    }


@app.get("/api/p7/rooms/{room_id}")
async def get_room(room_id: str) -> Dict[str, Any]:
    if CATALOG is None:
        raise HTTPException(status_code=503, detail="catalog not initialized")
    # Catalog row lookup is in-memory; safe to do directly.
    row = CATALOG.get_room_row(room_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"room {room_id!r} not in catalog")
    # Manifest load is disk I/O + JSON schema validation — offload to a
    # thread so we don't block the event loop. The CatalogLoader's
    # internal `threading.RLock` keeps it safe across threads.
    manifest = None
    manifest_error = None
    try:
        manifest = await asyncio.to_thread(CATALOG.get_manifest, room_id)
    except ManifestError as exc:
        # Log the detail (ManifestError messages include internal filesystem
        # paths) but return a generic message so we don't expose those paths to
        # the caller (CodeQL py/stack-trace-exposure).
        LOG.warning("manifest load failed for room %s: %s", room_id, exc)
        manifest_error = "manifest failed to load or validate"
    return {
        "catalog_row": row,
        "manifest": manifest,
        "manifest_error": manifest_error,
    }


@app.post("/api/p7/rooms/{room_id}/transition", dependencies=[Depends(require_http_control)])
async def transition_room(room_id: str, req: TransitionRequest) -> Dict[str, Any]:
    if ENGINE is None or PUBLISHER is None:
        raise HTTPException(status_code=503, detail="P7 service not ready")
    LOG.info("transition request: room=%s target=%s requester=%s reason=%s",
             room_id, req.target_stage, req.requester, req.reason)
    result = await ENGINE.transition(
        room_id=room_id,
        target_stage=req.target_stage,
        reason=req.reason,
        requester=req.requester,
    )
    return result


@app.post("/api/p7/rooms/{room_id}/session")
async def room_session(room_id: str, req: SessionRequest) -> Dict[str, Any]:
    """Open or close a room session.

    The OpenRoom desktop adapter (pmovesRoomAdapter.ts) calls this on
    room enter (action=open) and room leave (action=close). The endpoint
    is intentionally **unauthenticated** because the adapter is a
    public-facing browser-side module — auth would block the openroom
    reverse proxy from forwarding the call. The session is recorded
    with the agent_id + alter that the client supplies, so audit
    forensics still work (the alter is a soft signal, not an identity
    proof). For real auth, deploy a forward-auth gateway in front of
    /api/p7/.

    Best-effort NATS publish: if the broker is down, the session is
    still recorded in the local log and a session_id is returned so
    the desktop doesn't block. Catalog row lookup is in-memory; if
    the room isn't in the catalog we still record the session (it
    might be a private/owner-only room that doesn't appear in the
    public catalog).
    """
    if req.action not in ("open", "close"):
        raise HTTPException(
            status_code=400,
            detail=f"action must be 'open' or 'close', got {req.action!r}",
        )
    session_id = str(uuid.uuid4())
    LOG.info(
        "session %s: room=%s agent=%s alter=%s stage=%s session_id=%s",
        req.action, room_id, req.agent_id, req.alter, req.room_stage, session_id,
    )
    if PUBLISHER is not None:
        try:
            await PUBLISHER.publish_room_session(
                room_id=room_id,
                session_id=session_id,
                action=req.action,
                agent_id=req.agent_id,
                alter=req.alter,
                room_stage=req.room_stage,
            )
        except Exception:  # pragma: no cover - best-effort
            LOG.exception("session %s publish failed (continuing)", req.action)
    return {
        "status": {"open": "opened", "close": "closed"}[req.action],
        "session_id": session_id,
        "room_id": room_id,
        "agent_id": req.agent_id,
        "alter": req.alter,
        "room_stage": req.room_stage,
        "timestamp": req.timestamp or datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/p7/reload")
async def reload_catalog() -> Dict[str, Any]:
    if CATALOG is None or PUBLISHER is None:
        raise HTTPException(status_code=503, detail="P7 service not ready")
    # Catalog reload is disk I/O — offload to a thread.
    cat = await asyncio.to_thread(CATALOG.reload)
    rooms_loaded = len(cat.get("rooms", []))
    await PUBLISHER.publish_config_reloaded(
        schema_version=cat.get("schema_version", "?"),
        rooms_loaded=rooms_loaded,
    )
    return {
        "status": "reloaded",
        "schema_version": cat.get("schema_version", "?"),
        "rooms_loaded": rooms_loaded,
    }


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #

def main() -> None:
    """Run uvicorn programmatically. The Dockerfile runs `uvicorn main:app` from
    this service directory; this entrypoint is for local `python main.py` runs.
    """
    import uvicorn
    uvicorn.run(
        "main:app",
        host=SETTINGS.http_host,
        port=SETTINGS.http_port,
        log_level=SETTINGS.log_level.lower(),
    )


if __name__ == "__main__":
    main()
