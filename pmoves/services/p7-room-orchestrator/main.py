"""
P7 Room-Aware Stage Manager — FastAPI App
=========================================

Public HTTP API for room lifecycle management. Endpoints follow the spec at
`pmoves/docs/specs/p7-service-spec-2026-07-20.md`.

  GET  /healthz                                       service + catalog health
  GET  /api/p7/rooms                                  list rooms (catalog rows)
  GET  /api/p7/rooms/{room_id}                        room detail (manifest + stage)
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

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Annotated

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
import sys as _sys
_SERVICES_COMMON = Path(__file__).resolve().parents[3] / "services" / "common"
if str(_SERVICES_COMMON) not in _sys.path:
    _sys.path.insert(0, str(_SERVICES_COMMON))
try:
    from env import get_secret as _get_secret  # type: ignore
except ImportError:  # pragma: no cover
    def _get_secret(key: str, default: str | None = None) -> str | None:
        import os
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
    signing_key = os.environ.get("P7_SIGNING_KEY", "")
    PUBLISHER = NATSPublisher(
        nats_url=SETTINGS.nats_url,
        service_card_id=SETTINGS.service_card_id,
        connect_timeout_sec=SETTINGS.nats_connect_timeout_sec,
        retry_max_attempts=SETTINGS.nats_retry_max_attempts,
        retry_backoff_sec=SETTINGS.nats_retry_backoff_sec,
        signing_key=signing_key,
    )
    await PUBLISHER.connect()
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
    row = CATALOG.get_room_row(room_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"room {room_id!r} not in catalog")
    manifest = None
    manifest_error = None
    try:
        manifest = CATALOG.get_manifest(room_id)
    except ManifestError as exc:
        manifest_error = str(exc)
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


@app.post("/api/p7/reload")
async def reload_catalog() -> Dict[str, Any]:
    if CATALOG is None or PUBLISHER is None:
        raise HTTPException(status_code=503, detail="P7 service not ready")
    cat = CATALOG.reload()
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
