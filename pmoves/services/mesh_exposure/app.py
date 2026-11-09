"""mesh_exposure FastAPI app.

Service contract: see pmoves/docs/specs/pinokio-apps-registry-2026-07-28.md
(slice 4 docs commit). 6 endpoints (4 GET, 2 POST).

Port: 8132 (next to nats_event_bus :8131).
Auth: reads open; writes need X-PMOVES-Meshbus-Token (fail-closed).
"""
# NOTE: do NOT add `from __future__ import annotations` — Pydantic v2
# + FastAPI Body() need real class refs at runtime, not PEP 563 strings.
import logging
import os
import secrets
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

# Same dual-import pattern as nats_event_bus: try the docker image
# PYTHONPATH (pmoves/services/) first, fall back to the repo-relative path.
try:
    from .state import (
        DEFAULT_HEADSCALE_ACL,
        DEFAULT_REGISTRY_DIR,
        ApplyResult,
        ReconcilePlan,
        Registry,
        apply as apply_plan,
        default_headscale_reader,
        plan as plan_reconcile,
    )
except ImportError:  # pragma: no cover
    sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from mesh_exposure.state import (  # type: ignore
        DEFAULT_HEADSCALE_ACL,
        DEFAULT_REGISTRY_DIR,
        ApplyResult,
        ReconcilePlan,
        Registry,
        apply as apply_plan,
        default_headscale_reader,
        plan as plan_reconcile,
    )


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

PORT = int(os.environ.get("MESH_EXPOSURE_PORT", "8132"))
HOST = os.environ.get("MESH_EXPOSURE_HOST", "127.0.0.1")
REGISTRY_DIR = os.environ.get("MESH_EXPOSURE_REGISTRY_DIR", DEFAULT_REGISTRY_DIR)
HEADSCALE_ACL_PATH = os.environ.get("MESH_EXPOSURE_HEADSCALE_ACL", DEFAULT_HEADSCALE_ACL)
MESHBUS_TOKEN = os.environ.get("MESH_EXPOSURE_TOKEN", "")
# Per the slice-4 contract: the writers (cloudflared SSH, Cloudflare API,
# Hostinger API) are operator runbook territory in production. The
# service ships with noop writers; production runs the writer steps
# from the runbook (or the operator's wrapper script) against the
# ReconcilePlan JSON this service returns.
WRITER_MODE = os.environ.get("MESH_EXPOSURE_WRITER_MODE", "noop").lower()  # noop | apply


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mesh_exposure")


# --------------------------------------------------------------------------
# Pydantic
# --------------------------------------------------------------------------

class ApplyRequest(BaseModel):
    confirm: bool = Field(
        default=False,
        description="Must be true. A safety gate to prevent accidental writes — the caller must read the plan, decide, and re-send with confirm=true.",
    )


# --------------------------------------------------------------------------
# State: per-process mutable container for the live ReconcilePlan
# --------------------------------------------------------------------------

class ServiceState:
    """Per-process state. Two timestamps + the last plan.

    last_reconcile_at = the time of the most recent plan computation
    last_change_at    = the time of the most recent plan that had a non-noop diff
    last_plan         = the most recent ReconcilePlan (or None)"""

    def __init__(self):
        self.last_reconcile_at: Optional[str] = None
        self.last_change_at: Optional[str] = None
        self.last_plan: Optional[ReconcilePlan] = None
        self.last_apply: Optional[ApplyResult] = None
        self.last_apply_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_reconcile_at": self.last_reconcile_at,
            "last_change_at": self.last_change_at,
            "last_plan": self.last_plan.to_dict() if self.last_plan else None,
            "last_apply_at": self.last_apply_at,
            "last_apply": self.last_apply.to_dict() if self.last_apply else None,
        }


# --------------------------------------------------------------------------
# Default noop writers (the service ships with these; production
# overrides via env or runbook)
# --------------------------------------------------------------------------

def noop_headscale_writer(added: List[Dict[str, Any]], removed: List[Dict[str, Any]]) -> None:
    logger.info(
        "noop_headscale_writer called with %d added, %d removed "
        "(production runbook handles the actual write)",
        len(added), len(removed),
    )


def noop_cloudflared_writer(added: List[Dict[str, Any]], removed: List[Dict[str, Any]]) -> None:
    logger.info(
        "noop_cloudflared_writer called with %d added, %d removed "
        "(production runbook handles the actual write)",
        len(added), len(removed),
    )


def noop_dns_writer(added: List[Dict[str, Any]], removed: List[Dict[str, Any]]) -> None:
    logger.info(
        "noop_dns_writer called with %d added, %d removed "
        "(production runbook handles the actual write)",
        len(added), len(removed),
    )


# --------------------------------------------------------------------------
# App factory
# --------------------------------------------------------------------------

def create_app(
    registry: Optional[Registry] = None,
    state: Optional[ServiceState] = None,
    token: Optional[str] = None,
    headscale_reader=None,
    cloudflared_reader=None,
    dns_reader=None,
    headscale_writer=None,
    cloudflared_writer=None,
    dns_writer=None,
) -> FastAPI:
    """Create the FastAPI app. All dependencies are injectable for tests."""

    app = FastAPI(
        title="mesh_exposure",
        version="0.1.0",
        description=(
            "Reconciles the pinokio-apps registry to the live fleet (headscale "
            "ACL ports, cloudflared tunnel ingress, Cloudflare + Hostinger DNS). "
            "See the slice-4 deep-dive report + spec doc for the contract."
        ),
    )

    if registry is None:
        registry = Registry.load_from_dir(REGISTRY_DIR)
    if state is None:
        state = ServiceState()
    if token is None:
        token = MESHBUS_TOKEN
    if headscale_reader is None:
        headscale_reader = default_headscale_reader(HEADSCALE_ACL_PATH)
    if cloudflared_reader is None:
        cloudflared_reader = _default_cloudflared_reader
    if dns_reader is None:
        dns_reader = _default_dns_reader
    if headscale_writer is None:
        headscale_writer = noop_headscale_writer
    if cloudflared_writer is None:
        cloudflared_writer = noop_cloudflared_writer
    if dns_writer is None:
        dns_writer = noop_dns_writer

    app.state.registry = registry
    app.state.svc_state = state
    app.state.meshbus_token = token
    app.state.headscale_reader = headscale_reader
    app.state.cloudflared_reader = cloudflared_reader
    app.state.dns_reader = dns_reader
    app.state.headscale_writer = headscale_writer
    app.state.cloudflared_writer = cloudflared_writer
    app.state.dns_writer = dns_writer

    def require_token(
        x_pmoves_meshbus_token: Optional[str] = Header(default=None, alias="X-PMOVES-Meshbus-Token")
    ) -> None:
        """Fail-closed token check for write endpoints. Missing service
        token -> 503; wrong header -> 401."""
        if not app.state.meshbus_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "MESH_EXPOSURE_TOKEN not configured on the service. "
                    "Set it in the mesh_exposure service environment to enable writes."
                ),
            )
        if not x_pmoves_meshbus_token or not secrets.compare_digest(
            x_pmoves_meshbus_token, app.state.meshbus_token
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-PMOVES-Meshbus-Token header",
            )

    def compute_plan() -> ReconcilePlan:
        return plan_reconcile(
            app.state.registry,
            app.state.headscale_reader,
            app.state.cloudflared_reader,
            app.state.dns_reader,
        )

    # ----------------------------------------------------------------------
    # Health
    # ----------------------------------------------------------------------

    @app.get("/healthz")
    def healthz() -> Dict[str, Any]:
        return {
            "status": "ok",
            "registry_entries": len(app.state.registry),
            "writer_mode": WRITER_MODE,
            "writes_enabled": bool(app.state.meshbus_token),
            "last_reconcile_at": app.state.svc_state.last_reconcile_at,
            "last_change_at": app.state.svc_state.last_change_at,
            "ts": datetime.now(timezone.utc).isoformat() + "Z",
        }

    # ----------------------------------------------------------------------
    # Registry read
    # ----------------------------------------------------------------------

    @app.get("/v1/registry")
    def list_registry(slug: Optional[str] = Query(default=None)) -> Dict[str, Any]:
        if slug:
            entry = app.state.registry.get(slug)
            if entry is None:
                raise HTTPException(404, f"Unknown slug: {slug}")
            return {"slug": slug, "entry": entry}
        return {
            "count": len(app.state.registry),
            "entries": app.state.registry.all(),
        }

    # ----------------------------------------------------------------------
    # Reconcile: plan + apply
    # ----------------------------------------------------------------------

    @app.get("/v1/reconcile/plan")
    def get_plan() -> Dict[str, Any]:
        p = compute_plan()
        app.state.svc_state.last_plan = p
        app.state.svc_state.last_reconcile_at = datetime.now(timezone.utc).isoformat() + "Z"
        if not p.is_noop():
            app.state.svc_state.last_change_at = app.state.svc_state.last_reconcile_at
        return p.to_dict()

    @app.get("/v1/reconcile/status")
    def get_status() -> Dict[str, Any]:
        return app.state.svc_state.to_dict()

    @app.post("/v1/reconcile/apply", dependencies=[Depends(require_token)])
    def post_apply(req: ApplyRequest) -> Dict[str, Any]:
        if not req.confirm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "confirm must be true. GET /v1/reconcile/plan first, "
                    "review the diff, then re-send with confirm=true to apply."
                ),
            )
        if WRITER_MODE != "apply":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"WRITER_MODE={WRITER_MODE}; set MESH_EXPOSURE_WRITER_MODE=apply "
                    "to actually write. The default noop mode is for read-only use."
                ),
            )
        p = compute_plan()
        result = apply_plan(
            p,
            app.state.headscale_writer,
            app.state.cloudflared_writer,
            app.state.dns_writer,
        )
        app.state.svc_state.last_plan = p
        app.state.svc_state.last_reconcile_at = datetime.now(timezone.utc).isoformat() + "Z"
        if not p.is_noop():
            app.state.svc_state.last_change_at = app.state.svc_state.last_reconcile_at
        app.state.svc_state.last_apply = result
        app.state.svc_state.last_apply_at = app.state.svc_state.last_reconcile_at
        return result.to_dict()

    @app.post("/v1/reconcile/preview", dependencies=[Depends(require_token)])
    def post_preview(slug: str = Query(..., min_length=1)) -> Dict[str, Any]:
        """Dry-run for a single app: what would the plan look like if only
        this app were in the registry? Useful for the operator to verify
        a single app's network_exposure contract before the full reconcile."""
        entry = app.state.registry.get(slug)
        if entry is None:
            raise HTTPException(404, f"Unknown slug: {slug}")
        from .state import (
            desired_cloudflared_entries,
            desired_dns_records,
            desired_headscale_rules,
            diff_cloudflared,
            diff_dns,
            diff_headscale,
        )
        d_h = desired_headscale_rules(entry)
        d_c = desired_cloudflared_entries(entry)
        d_d = desired_dns_records(entry)
        a_h, r_h, u_h = diff_headscale(d_h, app.state.headscale_reader())
        a_c, r_c, u_c = diff_cloudflared(d_c, app.state.cloudflared_reader())
        a_d, r_d, u_d = diff_dns(d_d, app.state.dns_reader())
        return {
            "slug": slug,
            "headscale": {"added": a_h, "removed": r_h, "unchanged_count": u_h},
            "cloudflared": {"added": a_c, "removed": r_c, "unchanged_count": u_c},
            "dns": {"added": a_d, "removed": r_d, "unchanged_count": u_d},
        }

    return app


# --------------------------------------------------------------------------
# Default production readers (SSH to kvm2 + Cloudflare + Hostinger APIs)
#
# These are stubbed as no-ops in the default app because the production
# credentials (CLOUDFLARE_*, HOSTINGER_*, kvm2 SSH key) come from
# pmoves/config/mcp/{cloudflare,hostinger}.yaml + the CHIT secrets
# manifest, not from the service env. The slice-4 runbook
# (pmoves/docs/operations/MESH_EXPOSURE_RUNBOOK.md) documents the
# production reader steps; this service exposes the readers as
# injectable so the operator can wire them in.
# --------------------------------------------------------------------------

def _default_cloudflared_reader() -> List[Dict[str, Any]]:
    """Default cloudflared reader: returns []. Production: SSH to kvm2
    + cat /etc/cloudflared/config.yml + parse the ingress section.

    The slice-4 runbook documents the SSH command. We do NOT embed
    the SSH key path here — the operator wires it via the runbook."""
    logger.info("default cloudflared reader: returning []; production wires SSH-to-kvm2 via the runbook")
    return []


def _default_dns_reader() -> List[Dict[str, Any]]:
    """Default DNS reader: returns []. Production: Cloudflare API +
    Hostinger API. Credentials live in pmoves/config/mcp/{cloudflare,
    hostinger}.yaml + the CHIT secrets manifest. The slice-4 runbook
    documents the curl commands."""
    logger.info("default dns reader: returning []; production wires Cloudflare + Hostinger APIs via the runbook")
    return []


# Module-level app for `uvicorn mesh_exposure.app:app`
app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
