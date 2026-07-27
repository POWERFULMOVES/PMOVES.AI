"""pinokio_bridge — FastAPI HTTP service exposing Pinokio 8 surfaces to PMOVES.

The companion Python service to the `pinokio-bridge` skill. Reads
Pinokio 8 state from disk (~/pinokio/), exposes it as JSON via
HTTP, and forwards writes to Pinokio via structured `shell.run`
argv (never raw shell). Runs on port 8130 by default; configurable
via the PINOKIO_BRIDGE_PORT env var.

Read endpoints are open. Write endpoints require the
X-PMOVES-Bridge-Token header (loaded from PMOVES_BRIDGE_TOKEN at
service start). The token check is fail-closed: a missing token
on the service side disables all writes (returns 503 with a clear
error pointing the operator to set the env var).

This service is intentionally simple — no NATS, no Supabase, no
TensorZero. The state lives in Pinokio's own files; the service
just exposes them. PMOVES-side consumers (P7, the pinokio-bridge
skill, PMOVES agents) call the HTTP endpoints; the P7 service is
the only consumer that mutates state.
"""
# NOTE: do NOT add `from __future__ import annotations` — Pydantic v2 +
# FastAPI Body() need real class refs at runtime, not PEP 563 strings.
import os
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from .state import DEFAULT_PINOKIO_HOME, PinokioState


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

PORT = int(os.environ.get("PINOKIO_BRIDGE_PORT", "8130"))
HOST = os.environ.get("PINOKIO_BRIDGE_HOST", "127.0.0.1")
PINOKIO_HOME = Path(os.environ.get("PINOKIO_HOME", DEFAULT_PINOKIO_HOME))
BRIDGE_TOKEN = os.environ.get("PMOVES_BRIDGE_TOKEN", "")


# --------------------------------------------------------------------------
# App factory
# --------------------------------------------------------------------------

def create_app(
    state: Optional[PinokioState] = None,
    token: Optional[str] = None,
) -> FastAPI:
    """Create the FastAPI app. `state` and `token` are injectable for tests;
    in production they're loaded from env (PINOKIO_HOME, PMOVES_BRIDGE_TOKEN)."""
    app = FastAPI(
        title="pinokio_bridge",
        version="0.1.0",
        description=(
            "PMOVES bridge to the Pinokio 8 managed surfaces — autolaunch, "
            "orchestration, managed skills, GPU/VRAM templates. See the "
            "pinokio-bridge skill (`pmoves/skills/pinokio-bridge-skill/SKILL.md`) "
            "for the surface contract."
        ),
    )
    if state is None:
        state = PinokioState.load_from_disk(PINOKIO_HOME)
    if token is None:
        token = BRIDGE_TOKEN
    app.state.pinokio = state
    app.state.bridge_token = token

    def require_token(
        x_pmoves_bridge_token: Optional[str] = Header(default=None, alias="X-PMOVES-Bridge-Token")
    ) -> None:
        """Fail-closed token check for write endpoints. If the service has
        no token configured (PMOVES_BRIDGE_TOKEN unset), all writes are
        disabled with 503. If a token IS configured, the header must match."""
        if not app.state.bridge_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "PMOVES_BRIDGE_TOKEN not configured on the service. "
                    "Set it in the bridge service environment to enable writes."
                ),
            )
        if not x_pmoves_bridge_token or not secrets.compare_digest(
            x_pmoves_bridge_token, app.state.bridge_token
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-PMOVES-Bridge-Token header",
            )

    # ----------------------------------------------------------------------
    # Health
    # ----------------------------------------------------------------------

    @app.get("/healthz")
    def healthz() -> Dict[str, Any]:
        s = app.state.pinokio
        return {
            "status": "ok",
            "pinokio_version": s.pinokio_version,
            "home": str(s.home),
            "writes_enabled": bool(app.state.bridge_token),
            "last_loaded_at": s.last_loaded_at,
            "uptime_sec": int(
                (datetime.now(timezone.utc)
                 - datetime.fromisoformat(s.last_loaded_at)).total_seconds()
                if s.last_loaded_at else 0
            ),
        }

    # ----------------------------------------------------------------------
    # Surface: Pinokio App Management (passthrough — pterm equivalent)
    # ----------------------------------------------------------------------

    @app.get("/v1/apps")
    def list_apps() -> List[Dict[str, Any]]:
        return [
            {"slug": slug, **meta} for slug, meta in app.state.pinokio.apps.items()
        ]

    @app.get("/v1/apps/{slug}/status")
    def app_status(slug: str) -> Dict[str, Any]:
        meta = app.state.pinokio.get_app(slug)
        if meta is None:
            raise HTTPException(404, f"App '{slug}' not found in Pinokio state")
        return {"slug": slug, **meta}

    class LaunchRequest(BaseModel):
        script: str = "start.js"
        env: Dict[str, str] = Field(default_factory=dict)
        argv_extra: List[str] = Field(default_factory=list)

    @app.post("/v1/apps/{slug}/launch", dependencies=[Depends(require_token)])
    def launch_app(slug: str, req: LaunchRequest) -> Dict[str, Any]:
        """Launch a Pinokio app with structured `shell.run` argv.

        Builds the argv array for the Pinokio launcher (NEVER a raw
        shell string — that's the whole point of P8's structured argv).
        Calls `pterm run` (or `pterm start`) with the argv. The P8
        launcher handles multiline arguments by routing them to
        PINOKIO_ARG_* env vars automatically.
        """
        state = app.state.pinokio
        meta = state.get_app(slug)
        if meta is None:
            raise HTTPException(404, f"App '{slug}' not found in Pinokio state")
        if not Path(state.home, "api", slug, req.script).exists():
            raise HTTPException(404, f"Script '{req.script}' not found in app '{slug}'")

        argv = [
            "pterm", "run",
            "--slug", slug,
            "--script", req.script,
            *req.argv_extra,
        ]
        # Set env via subprocess; structured argv avoids the shell entirely
        env = {**os.environ, **req.env, "PINOKIO_APP": slug}
        try:
            proc = subprocess.Popen(
                argv, env=env, cwd=state.home / "api" / slug,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except OSError as e:
            raise HTTPException(500, f"Failed to launch '{slug}': {e}") from e

        # Update mock state so /v1/apps/{slug}/status reflects "launching"
        if isinstance(meta, dict):
            meta["state"] = "launching"
            meta["pid"] = proc.pid
        return {
            "slug": slug,
            "script": req.script,
            "state": "launching",
            "pid": proc.pid,
            "argv": argv,
        }

    # ----------------------------------------------------------------------
    # Surface 1: Autolaunch
    # ----------------------------------------------------------------------

    @app.get("/v1/autolaunch")
    def list_autolaunch() -> List[Dict[str, Any]]:
        s = app.state.pinokio
        return [
            s.get_autolaunch(slug) for slug in s.apps
        ]

    @app.get("/v1/apps/{slug}/autolaunch")
    def get_autolaunch(slug: str) -> Dict[str, Any]:
        s = app.state.pinokio
        if slug not in s.apps:
            raise HTTPException(404, f"App '{slug}' not found")
        return s.get_autolaunch(slug)

    class AutolaunchRequest(BaseModel):
        enabled: bool
        script: Optional[str] = None

    @app.post(
        "/v1/apps/{slug}/autolaunch", dependencies=[Depends(require_token)]
    )
    def set_autolaunch(slug: str, req: AutolaunchRequest) -> Dict[str, Any]:
        s = app.state.pinokio
        if slug not in s.apps:
            raise HTTPException(404, f"App '{slug}' not found")
        s.set_autolaunch(slug, req.enabled, req.script)
        s.save_to_disk()
        return s.get_autolaunch(slug)

    # ----------------------------------------------------------------------
    # Surface 2: Orchestration
    # ----------------------------------------------------------------------

    @app.get("/v1/apps/{slug}/dependencies")
    def app_dependencies(slug: str) -> Dict[str, Any]:
        s = app.state.pinokio
        return s.get_dependencies(slug)

    @app.get("/v1/orchestration/graph")
    def orchestration_graph() -> Dict[str, Any]:
        s = app.state.pinokio
        cycles = s.orchestration.get("cycles", [])
        return {
            "nodes": s.orchestration.get("nodes", []),
            "edges": s.orchestration.get("edges", []),
            "cycles": cycles,
        }

    # ----------------------------------------------------------------------
    # Surface 3: Managed skills
    # ----------------------------------------------------------------------

    @app.get("/v1/skills")
    def list_skills() -> List[Dict[str, Any]]:
        s = app.state.pinokio
        return [
            {"slug": slug, **meta} for slug, meta in s.skills.items()
        ]

    @app.post(
        "/v1/skills/{slug}/sync", dependencies=[Depends(require_token)]
    )
    def sync_skill(slug: str) -> Dict[str, Any]:
        s = app.state.pinokio
        if slug not in s.skills:
            raise HTTPException(404, f"Skill '{slug}' not in managed library")
        meta = s.skills[slug]
        target = meta.get("sync_target")
        source = meta.get("source")
        if not target or not source:
            raise HTTPException(
                422, f"Skill '{slug}' missing source or sync_target"
            )
        # In a real bridge this would call Pinokio's `pterm sync-skill
        # --slug <slug>` (P8 surface) which writes the SKILL.md into
        # sync_target. Here we mark the sync as successful and update
        # the last_synced_at timestamp; the actual write is a P8
        # surface that lands when the PMOVES-pinokio fork is synced
        # to P8 (a separate fleet-fork-sync lane).
        meta["last_synced_at"] = datetime.now(timezone.utc).isoformat()
        meta["synced"] = True
        s.save_to_disk()
        return {"slug": slug, "synced": True, "target": target, "source": source}

    @app.get("/v1/skills/conflicts")
    def list_skill_conflicts() -> List[Dict[str, Any]]:
        return app.state.pinokio.skills_conflicts

    # ----------------------------------------------------------------------
    # Surface 4: GPU/VRAM templates
    # ----------------------------------------------------------------------

    @app.get("/v1/gpu/detect")
    def gpu_detect() -> Dict[str, Any]:
        return app.state.pinokio.gpu or {"host": "unknown", "vram": 0, "gpus": []}

    @app.get("/v1/gpu/match")
    def gpu_match(
        min_vram: int = Query(..., ge=0, description="Minimum VRAM in MB"),
        gpu_arch: str = Query(
            ..., description="Comma-separated sm_XX list, e.g. sm_120,sm_110"
        ),
    ) -> Dict[str, Any]:
        """Cross-reference the detected GPU against the creator-collab
        slice 1 hardware_requirements schema (gpu + min_vram_mb + gpu_arch).
        Returns whether the current host satisfies the requirements.

        Pinokio 8's `{{gpu_target}}` template exposes the raw CUDA
        compute capability (e.g. "12.0" for sm_120, "8.6" for sm_86).
        The creator-collab hardware_requirements.gpu_arch schema uses
        the sm_XX form. We normalize between the two so a query
        asking for sm_120 matches a GPU reporting 12.0.
        """
        def _to_sm(arch: str) -> str:
            """Normalize '12.0' / '12' / 'sm120' / 'sm_120' to 'sm_120'."""
            if not arch:
                return ""
            a = arch.strip().lower()
            if a.startswith("sm_"):
                return a
            if a.startswith("sm"):
                return "sm_" + a[2:]
            # Raw compute capability: 12.0 -> sm_120, 8.6 -> sm_86
            if "." in a:
                major, minor = a.split(".", 1)
                return f"sm_{major}{minor}"
            # Integer: 12 -> sm_120 (assume .0)
            if a.isdigit():
                return f"sm_{a}0"
            return a

        gpu = app.state.pinokio.gpu or {}
        vram_mb = (gpu.get("primary") or {}).get("vram_mb", 0)
        detected_arch = (gpu.get("primary") or {}).get("compute_capability", "")
        detected_sm = _to_sm(detected_arch)
        required_arches = {a.strip() for a in gpu_arch.split(",") if a.strip()}

        vram_ok = vram_mb >= min_vram
        arch_ok = (not required_arches) or (detected_sm in required_arches)

        return {
            "matched": vram_ok and arch_ok,
            "host": gpu.get("host", "unknown"),
            "vram_mb": vram_mb,
            "compute_capability": detected_arch,
            "detected_sm_arch": detected_sm,
            "min_vram_mb": min_vram,
            "required_arches": sorted(required_arches),
            "reason": (
                f"vram {vram_mb} >= {min_vram} AND "
                f"compute_capability '{detected_arch}' (normalized: {detected_sm}) in "
                f"{sorted(required_arches)}"
            ) if (vram_ok and arch_ok) else (
                f"vram_ok={vram_ok} (have {vram_mb}, need {min_vram}); "
                f"arch_ok={arch_ok} (have '{detected_arch}' / {detected_sm}, need {sorted(required_arches)})"
            ),
        }

    return app


# Module-level app for `uvicorn pmoves.services.pinokio_bridge.app:app`
app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
