from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastapi import Body, Depends, FastAPI, HTTPException, Response
from nats.aio.client import Client as NATS
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field, HttpUrl

# NATS service announcement integration
try:
    from services.common.nats_service_listener import announce_service, ServiceTier
    NATS_ANNOUNCE_AVAILABLE = True
except ImportError:
    NATS_ANNOUNCE_AVAILABLE = False

try:
    _services_root = Path(__file__).resolve().parents[2]
    if str(_services_root) not in sys.path:
        sys.path.insert(0, str(_services_root))
except Exception:
    pass

from services.common.events import envelope

logger = logging.getLogger("archon.main")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
PORT = int(os.environ.get("PORT", 8090))


def _strip_rest_suffix(url: str) -> str:
    trimmed = url.rstrip("/")
    suffix = "/rest/v1"
    if trimmed.endswith(suffix):
        return trimmed[: -len(suffix)]
    return trimmed


def _ensure_supabase_env() -> None:
    """Populate SUPABASE_* from explicit env without implicit fallbacks.

    Priority:
      1) ARCHON_SUPABASE_BASE_URL
      2) SUPA_REST_URL (stripped to base)
      3) Existing SUPABASE_URL (left as-is)
    No default to postgrest; caller must supply a reachable base (e.g., host.docker.internal:54321).
    """

    forced = (os.environ.get("ARCHON_SUPABASE_BASE_URL") or "").strip()
    rest = (os.environ.get("SUPA_REST_URL") or os.environ.get("SUPABASE_REST_URL") or "").strip()
    if forced:
        os.environ["SUPABASE_URL"] = _strip_rest_suffix(forced)
    elif rest:
        os.environ["SUPABASE_URL"] = _strip_rest_suffix(rest)
    # else: leave SUPABASE_URL unchanged if already set

    # Ensure downstream clients find the service role key under expected aliases.
    srv = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if srv:
        if not os.environ.get("SUPABASE_KEY"):
            os.environ["SUPABASE_KEY"] = srv
        if not os.environ.get("SUPABASE_SERVICE_KEY"):
            os.environ["SUPABASE_SERVICE_KEY"] = srv

    os.environ["POSTGRES_HOST"] = os.environ.get("PGHOST", "postgres")


_ensure_supabase_env()


async def _check_tensorzero_connectivity(base_url: str) -> bool:
    """Check if TensorZero is reachable at the given URL.

    Args:
        base_url: The OpenAI-compatible base URL to check.

    Returns:
        True if reachable, False otherwise.
    """
    try:
        import httpx
        # Test the /models endpoint which all TensorZero deployments expose
        test_url = base_url.replace("/openai/v1", "").replace("/openai", "")
        test_url = f"{test_url.rstrip('/')}/models"

        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(test_url)
            return response.status_code == 200
    except Exception:
        return False


def _check_tensorzero_sync(base_url: str) -> bool:
    """Synchronous wrapper for TensorZero connectivity check.

    Args:
        base_url: The OpenAI-compatible base URL to check.

    Returns:
        True if reachable, False otherwise.
    """
    try:
        # Run async check in new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_check_tensorzero_connectivity(base_url))
        finally:
            loop.close()
    except Exception:
        return False


def _tensorzero_openai_base() -> str:
    """Return OpenAI-compatible base URL from TensorZero settings.

    Priority for hybrid standalone mode:
      1) TENSORZERO_BASE_URL (explicit, backward compatible)
      2) TENSORZERO_URL (parent PMOVES.AI TensorZero)
      3) host.docker.internal:3030 (hybrid mode default)

    Returns:
        OpenAI-compatible base URL or empty string if not configured.
    """
    # First, check explicit TENSORZERO_BASE_URL (backward compatibility)
    base = (os.environ.get("TENSORZERO_BASE_URL") or "").strip()
    if not base:
        # Check for parent PMOVES.AI TensorZero in hybrid standalone mode
        parent_tensorzero = os.environ.get("TENSORZERO_URL")
        if parent_tensorzero:
            base = parent_tensorzero
        else:
            # Fallback to host.docker.internal for hybrid mode
            # This allows submodule to reach parent PMOVES.AI TensorZero
            docked_mode = os.environ.get("DOCKED_MODE", "false").lower() == "true"
            if not docked_mode:
                # In standalone mode, try parent via host.docker.internal
                base = "http://host.docker.internal:3030"

    if not base:
        return ""

    base = base.rstrip("/")
    if base.endswith("/openai/v1"):
        return base
    if base.endswith("/openai"):
        return f"{base.rstrip('/')}/v1"
    return f"{base}/openai/v1"


def _sync_openai_compat_env() -> None:
    """Sync TensorZero settings to OpenAI environment variables.

    In hybrid standalone mode, verifies connectivity to parent TensorZero
    via host.docker.internal and falls back gracefully if unreachable.
    """
    resolved_base = ""
    for candidate in (
        os.environ.get("OPENAI_COMPATIBLE_BASE_URL"),
        os.environ.get("OPENAI_API_BASE"),
        _tensorzero_openai_base(),
    ):
        value = (candidate or "").strip()
        if value:
            resolved_base = value
            break

    if resolved_base:
        # In hybrid mode, verify connectivity to parent TensorZero
        if "host.docker.internal" in resolved_base:
            if _check_tensorzero_sync(resolved_base):
                logger.info("TensorZero reachable at %s (hybrid mode)", resolved_base)
            else:
                logger.warning(
                    "TensorZero unreachable at %s (hybrid mode). "
                    "Ensure PMOVES.AI is running or set TENSORZERO_URL explicitly.",
                    resolved_base
                )
                # Don't set unreachable base - allow fallback to direct OpenAI
                resolved_base = ""

    if resolved_base:
        targets = (
            "OPENAI_COMPATIBLE_BASE_URL",
            "OPENAI_API_BASE",
            "OPENAI_COMPATIBLE_BASE_URL_LLM",
            "OPENAI_COMPATIBLE_BASE_URL_EMBEDDING",
            "OPENAI_COMPATIBLE_BASE_URL_TTS",
            "OPENAI_COMPATIBLE_BASE_URL_STT",
        )
        updated = []
        for target in targets:
            current = (os.environ.get(target) or "").strip()
            if current:
                continue
            os.environ[target] = resolved_base
            os.putenv(target, resolved_base)
            updated.append(target)
        if updated:
            logger.info("OpenAI-compatible base resolved to %s", resolved_base)
        else:
            logger.debug("OpenAI-compatible base already set to %s", resolved_base)
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        tz_key = (os.environ.get("TENSORZERO_API_KEY") or "").strip()
        if tz_key:
            os.environ["OPENAI_API_KEY"] = tz_key
            os.putenv("OPENAI_API_KEY", tz_key)
            logger.info("OpenAI-compatible API key derived from TensorZero settings")


_sync_openai_compat_env()

from .orchestrator import ArchonOrchestrator


class CrawlJob(BaseModel):
    url: HttpUrl
    task_id: Optional[str] = None
    depth: Optional[int] = Field(default=None, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ArchonService:
    def __init__(self, *, nats_url: str = NATS_URL) -> None:
        self._nats_url = nats_url
        self._nc: Optional[NATS] = None
        self._ready = asyncio.Event()
        self._logger = logging.getLogger("archon.service")
        self._subscriptions = (
            "archon.crawl.request",
            "archon.crawl.request.v1",
            "ingest.document.ready.v1",
            "ingest.file.added.v1",
            "ingest.transcript.ready.v1",
        )
        self.orchestrator = ArchonOrchestrator(self.publish_event, logger=logging.getLogger("archon.orchestrator"))

    @property
    def is_connected(self) -> bool:
        return self._ready.is_set()

    async def start(self) -> None:
        if self._nc is not None:
            return
        self._logger.info("Connecting to NATS at %s", self._nats_url)
        self._nc = NATS()
        await self._nc.connect(servers=[self._nats_url])
        for subject in self._subscriptions:
            await self._nc.subscribe(subject, cb=self._on_message)
        self._ready.set()
        self._logger.info("Archon service connected and subscriptions registered")

    async def stop(self) -> None:
        if self._nc is None:
            return
        self._logger.info("Draining NATS connection")
        await self.orchestrator.shutdown()
        try:
            await self._nc.drain()
        finally:
            await self._nc.close()
            self._nc = None
            self._ready.clear()
        self._logger.info("Archon service disconnected")

    async def publish_event(
        self,
        topic: str,
        payload: Dict[str, Any],
        *,
        correlation_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        source: str = "archon",
    ) -> Dict[str, Any]:
        await self._ready.wait()
        assert self._nc is not None
        env = envelope(topic, payload, correlation_id=correlation_id, parent_id=parent_id, source=source)
        await self._nc.publish(topic, json.dumps(env).encode("utf-8"))
        await self._nc.flush()
        return env

    async def handle_local_event(
        self,
        topic: str,
        payload: Dict[str, Any],
        *,
        correlation_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        source: str = "archon",
    ) -> Any:
        env = envelope(topic, payload, correlation_id=correlation_id, parent_id=parent_id, source=source)
        return await self.orchestrator.dispatch(topic, env)

    async def _on_message(self, msg) -> None:
        data: Dict[str, Any]
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except json.JSONDecodeError:
            self._logger.exception("Invalid JSON received on %s", msg.subject)
            return
        if not isinstance(data, dict):
            self._logger.warning("Dropping non-dict payload from %s", msg.subject)
            return
        data.setdefault("topic", msg.subject)
        await self.orchestrator.dispatch(msg.subject, data)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Archon service")
    service = ArchonService()
    await service.start()
    app.state.service = service
    try:
        yield
    finally:
        logger.info("Stopping Archon service")
        await service.stop()


app = FastAPI(title="Archon (PMOVES v5)", lifespan=lifespan)


def get_archon_service() -> ArchonService:
    service = getattr(app.state, "service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Archon service unavailable")
    return service


@app.get("/healthz")
async def healthz(service: ArchonService = Depends(get_archon_service)) -> Dict[str, Any]:
    status = "ok" if service.is_connected else "degraded"
    return {"status": status, "service": "archon", "nats": service.is_connected}


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint for observability."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/events/publish")
async def events_publish(
    body: Dict[str, Any] = Body(...),
    service: ArchonService = Depends(get_archon_service),
) -> Dict[str, Any]:
    topic = body.get("topic")
    if not topic:
        raise HTTPException(status_code=422, detail="topic is required")
    payload = body.get("payload") or {}
    env = await service.publish_event(topic, payload, source="archon.api")
    return {"published": topic, "id": env["id"]}


@app.post("/archon/crawl")
async def submit_crawl(
    job: CrawlJob,
    service: ArchonService = Depends(get_archon_service),
) -> Dict[str, Any]:
    payload = job.model_dump(exclude_none=True)
    task_id = payload.get("task_id") or str(uuid.uuid4())
    payload["task_id"] = task_id
    await service.publish_event("archon.crawl.request.v1", payload, source="archon.api")
    return {"task_id": task_id}


@app.get("/tasks/{task_id}")
async def get_task(task_id: str, service: ArchonService = Depends(get_archon_service)) -> Dict[str, Any]:
    snapshot = await service.orchestrator.snapshot_tasks()
    task = snapshot.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task_id": task_id, **task}


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=os.environ.get("ARCHON_LOG_LEVEL", "INFO"))
    uvicorn.run("services.archon.main:app", host="0.0.0.0", port=PORT, reload=False)

"""Launch the vendored Archon stack within the PMOVES runtime.

This entrypoint bootstraps the upstream Archon application that is vendored
under ``vendor/archon`` and ensures the related microservices (the MCP HTTP
bridge and the lightweight agent worker pool) are launched alongside the main
FastAPI server. The goal is to provide a drop-in compatible process for the
Archon UI/IDE clients so all REST and streaming endpoints work as expected.
"""

import asyncio
import logging
import os
import sys
from contextlib import suppress
from importlib import import_module
from pathlib import Path
from typing import Optional

import uvicorn
import httpx


LOGGER = logging.getLogger("pmoves.archon")


def _resolve_vendor_paths() -> tuple[Path, Path, Path]:
    """Return the Archon vendor, python root, and python ``src`` directory."""

    env_root = os.environ.get("ARCHON_VENDOR_ROOT")
    if env_root:
        vendor_root = Path(env_root).expanduser().resolve()
    else:
        service_dir = Path(__file__).resolve().parent
        vendor_root = None
        for parent in (service_dir, *service_dir.parents):
            candidate = (parent / "vendor" / "archon").resolve()
            if candidate.exists():
                vendor_root = candidate
                break
        if vendor_root is None:  # pragma: no cover - build-time guard
            raise RuntimeError(
                "Unable to locate Archon vendor checkout. Set ARCHON_VENDOR_ROOT "
                "to the upstream Archon repository path or ensure vendor/archon is present."
            )

    python_root = vendor_root / "python"
    python_src = python_root / "src"

    if not python_src.exists():  # pragma: no cover - validation guard
        raise RuntimeError(
            "Archon vendor sources were not found. Expected to see "
            f"{python_src}. Ensure the upstream Archon repository is available."
        )

    return vendor_root, python_root, python_src


def _normalize_supabase_env() -> None:
    """Record the base PostgREST URL for downstream patches."""

    for key in ("ARCHON_SUPABASE_BASE_URL", "SUPA_REST_URL", "SUPABASE_URL"):
        url = os.environ.get(key)
        if not url:
            continue
        os.environ["ARCHON_SUPABASE_BASE_URL"] = _strip_rest_suffix(url)
        break


_normalize_supabase_env()

_, ARCHON_PYTHON_ROOT, ARCHON_SRC = _resolve_vendor_paths()

if str(ARCHON_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(ARCHON_PYTHON_ROOT))

if str(ARCHON_SRC) not in sys.path:
    sys.path.insert(0, str(ARCHON_SRC))


def _patch_supabase_validation() -> None:
    """Relax upstream Supabase URL checks for in-network HTTP hosts.

    Archon insists on HTTPS for non-local hosts. Our compose stack exposes
    PostgREST at `http://postgrest:3000`, which is safe on the private Docker
    network. We patch the validator so that the hostname derived from
    ``SUPABASE_URL`` (and any optional override via ARCHON_HTTP_ALLOW_HOSTS)
    is treated as local.
    """

    allow_hosts = set(
        h.strip() for h in os.environ.get("ARCHON_HTTP_ALLOW_HOSTS", "").split(",") if h.strip()
    )
    supabase_url = os.environ.get("SUPABASE_URL")
    if supabase_url:
        from urllib.parse import urlparse

        host = urlparse(supabase_url).hostname
        if host:
            allow_hosts.add(host)

    if not allow_hosts:
        return

    try:
        from server.config import config as vendor_config  # type: ignore
    except ImportError:
        return

    original_validate = vendor_config.validate_supabase_url

    def patched_validate(url: str) -> bool:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme == "http" and (parsed.hostname or "") in allow_hosts:
            return True
        return original_validate(url)

    vendor_config.validate_supabase_url = patched_validate  # type: ignore[attr-defined]


_patch_supabase_validation()


def _patch_supabase_client() -> None:
    """Ensure Supabase client uses raw PostgREST root inside compose."""

    base_url = os.environ.get("ARCHON_SUPABASE_BASE_URL", "")
    if not base_url or "supabase.co" in base_url:
        return

    def _configure_client(client):
        root = base_url.rstrip("/")
        if root.endswith("/rest/v1"):
            rest_url = root
        elif root.endswith("/rest"):
            rest_url = f"{root}/v1"
        else:
            parsed = urlparse(root)
            hostname = (parsed.hostname or "").lower()
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if "postgrest" in hostname or (hostname in {"localhost", "127.0.0.1"} and port == 3000):
                rest_url = root
            else:
                rest_url = f"{root}/rest/v1"

        client.rest_url = rest_url
        client._postgrest = None  # type: ignore[attr-defined]
        return client

    try:
        from server.services.credential_service import CredentialService  # type: ignore
    except ImportError:
        return

    original_get_client = CredentialService._get_supabase_client  # type: ignore[attr-defined]

    def wrapped(self):  # type: ignore[override]
        client = original_get_client(self)
        return _configure_client(client)

    CredentialService._get_supabase_client = wrapped  # type: ignore[attr-defined]

    try:
        import server.services.client_manager as client_manager  # type: ignore
    except ImportError:
        return

    original_manager_get = client_manager.get_supabase_client

    def manager_wrapper():
        client = original_manager_get()
        return _configure_client(client)

    client_manager.get_supabase_client = manager_wrapper  # type: ignore[assignment]


_patch_supabase_client()


def _patch_mcp_status_response() -> None:
    """Normalize MCP status responses when Docker is unavailable."""

    try:
        from server.api_routes import mcp_api  # type: ignore
    except ImportError:  # pragma: no cover - vendor guard
        LOGGER.debug("Skipping MCP status patch; vendor module missing")
        return

    original_get_container_status = getattr(mcp_api, "get_container_status", None)
    if original_get_container_status is None:  # pragma: no cover - defensive guard
        LOGGER.debug("Skipping MCP status patch; get_container_status missing")
        return

    def patched_get_container_status():  # type: ignore[override]
        try:
            status = original_get_container_status()
        except Exception as exc:  # pragma: no cover - defensive fallback
            message = str(exc)
            lowered = message.lower()
            if "filenotfounderror" in lowered or "permission denied" in lowered or "connection aborted" in lowered:
                return {
                    "status": "unavailable",
                    "uptime": None,
                    "logs": [],
                    "container_status": "unavailable",
                    "message": "Docker daemon unreachable. Mount /var/run/docker.sock or disable MCP container checks.",
                    "details": message,
                }
            raise

        if isinstance(status, dict):
            error_text = status.get("error")
            if error_text:
                normalized = str(error_text).lower()
                if "filenotfounderror" in normalized or "permission denied" in normalized or "connection aborted" in normalized:
                    patched = dict(status)
                    patched["status"] = "unavailable"
                    patched["container_status"] = "unavailable"
                    patched.setdefault("logs", [])
                    patched["message"] = (
                        "Docker daemon unreachable. Mount /var/run/docker.sock or disable MCP container checks."
                    )
                    patched["details"] = str(error_text)
                    patched.pop("error", None)
                    return patched

        return status

    mcp_api.get_container_status = patched_get_container_status  # type: ignore[assignment]


_patch_mcp_status_response()


def _ensure_env_defaults() -> dict[str, str]:
    """Populate default environment variables for Archon services."""

    env = os.environ
    port = int(env.get("PORT") or env.get("ARCHON_SERVER_PORT", "8090"))
    env.setdefault("ARCHON_SERVER_PORT", str(port))
    env.setdefault("ARCHON_MCP_PORT", "8051")
    env.setdefault("ARCHON_AGENTS_PORT", "8052")
    env.setdefault("ARCHON_SERVER_HOST", "localhost")
    env.setdefault("ARCHON_MCP_HOST", "localhost")
    env.setdefault("ARCHON_AGENTS_HOST", "localhost")
    env.setdefault("MCP_SERVICE_URL", f"http://localhost:{env['ARCHON_MCP_PORT']}")

    return {
        "server_port": env["ARCHON_SERVER_PORT"],
        "mcp_port": env["ARCHON_MCP_PORT"],
        "agents_port": env["ARCHON_AGENTS_PORT"],
    }


ENV_PORTS = _ensure_env_defaults()


def _build_pythonpath_env() -> str:
    """Return a PYTHONPATH string that ensures vendor modules are importable."""

    python_paths = [str(ARCHON_PYTHON_ROOT), str(ARCHON_SRC)]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        python_paths.append(existing)
    return os.pathsep.join(python_paths)


def _import_archon_app():
    """Import the upstream Archon FastAPI application.

    If vendor import fails, serve a minimal placeholder app exposing health
    endpoints so the container starts and reports diagnostics instead of
    crashing. This keeps compose health and logs available for troubleshooting.
    """

    try:
        archon_main = import_module("server.main")
        return archon_main.app
    except ModuleNotFoundError as exc:  # pragma: no cover - defensive guard
        logger.exception("Archon vendor import failed: %s", exc)

        fallback = FastAPI(title="Archon (placeholder)")

        @fallback.get("/")
        async def root():  # type: ignore[no-redef]
            return {
                "status": "degraded",
                "message": "Archon vendor module not found. Check ARCHON_VENDOR_ROOT or rebuild image.",
            }

        @fallback.get("/healthz")
        async def health():  # type: ignore[no-redef]
            try:
                result = await _pmoves_healthcheck()
                return result
            except HTTPException as he:
                raise he

        @fallback.get("/ready")
        async def ready():  # type: ignore[no-redef]
            try:
                result = await _pmoves_ready()
                return result
            except HTTPException as he:
                raise he

        return fallback


FORCE_PLACEHOLDER = os.environ.get("ARCHON_VENDOR_FORCE_PLACEHOLDER", "").strip().lower() in {"1","true","yes"}
app = _import_archon_app() if not FORCE_PLACEHOLDER else FastAPI(title="Archon (placeholder)")

# Re-sync OpenAI-compatible env after the vendored app loads, since upstream imports
# may mutate OpenAI-compatible environment variables.
_sync_openai_compat_env()


@app.get("/healthz")
async def _pmoves_healthcheck():
    # Prefer the configured Supabase base URL for health checks.
    # For Supabase CLI (aggregated gateway on :65421), probe a concrete REST
    # table endpoint (`/rest/v1/archon_settings`) instead of the root path.
    supabase = os.environ.get("SUPABASE_URL") or os.environ.get("SUPA_REST_URL") or ""
    ok = True
    code = 0
    error = None
    if supabase:
        base = supabase.rstrip("/")
        target = base
        try:
            parsed = urlparse(base)
            host = (parsed.hostname or "").lower()
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            # Supabase CLI default REST gateway OR internal Kong gateway:
            # hit a known table so 404 on `/` or bare `/rest/v1` does not
            # falsely mark the stack unhealthy.
            is_supabase_cli = host in {"host.docker.internal", "127.0.0.1", "localhost"} and port == 65421
            is_kong_gateway = host == "supabase_kong_pmoves.ai" and port == 8000
            if is_supabase_cli or is_kong_gateway:
                target = f"{base}/rest/v1/archon_settings?select=*"
        except Exception:
            target = base

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(target)
                code = r.status_code
                # Treat 200 and 400-series schema errors as "reachable"; only 5xx/000 mark unhealthy.
                if 200 <= code < 300:
                    ok = True
                elif 400 <= code < 500:
                    ok = True
                    error = f"supabase client error {code}"
                else:
                    ok = False
        except Exception as exc:  # pragma: no cover - defensive network guard
            ok = False
            error = str(exc)

    payload = {"status": "ok" if ok else "degraded", "service": "archon", "supabase": {"url": supabase, "http": code}}
    if error:
        payload["error"] = error
    if ok:
        return payload
    raise HTTPException(status_code=503, detail=payload)


@app.get("/ready")
async def _pmoves_ready():
    details = {}
    # NATS probe
    nats_ok = False
    try:
        # Shallow TCP probe to NATS
        parsed = urlparse(NATS_URL)
        host = parsed.hostname or "nats"
        port = parsed.port or 4222
        with socket.create_connection((host, port), timeout=1.5):
            nats_ok = True
    except OSError:
        nats_ok = False

    # Supabase/PostgREST probe via health
    try:
        result = await _pmoves_healthcheck()
        sb_ok = result.get("status") == "ok"
        details["supabase"] = result.get("supabase", {})
    except HTTPException as exc:  # 503 captures details
        sb_ok = False
        try:
            details.update(exc.detail)  # type: ignore[arg-type]
        except Exception:
            details["supabase"] = {"url": os.environ.get("SUPABASE_URL")}

    ready = nats_ok and sb_ok
    status = {"status": "ready" if ready else "not_ready", "nats": nats_ok, **details}
    if ready:
        return status
    raise HTTPException(status_code=503, detail=status)


@app.get("/mcp/describe")
async def _pmoves_mcp_describe():
    """Lightweight JSON capability shim for the MCP bridge.

    Tries a few common probe paths against the local MCP HTTP bridge and
    reports reachability + status codes without assuming a specific
    upstream route shape.
    """
    host = os.environ.get("ARCHON_MCP_HOST", "localhost")
    port = int(os.environ.get("ARCHON_MCP_PORT", "8051"))
    base = f"http://{host}:{port}"
    probes = {"/": None, "/health": None, "/tools": None, "/openapi.json": None}
    reachable = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            for path in list(probes.keys()):
                try:
                    r = await client.get(f"{base}{path}")
                    probes[path] = r.status_code
                    if 100 <= r.status_code < 600:
                        reachable = True
                except Exception:
                    probes[path] = 0
    except Exception:
        pass

    return {
        "endpoint": base,
        "reachable": reachable,
        "probes": probes,
    }


async def _proxy_to_mcp(path: str, *, method: str = "GET", json_body: Optional[dict] = None) -> httpx.Response:
    host = os.environ.get("ARCHON_MCP_HOST", "localhost")
    port = int(os.environ.get("ARCHON_MCP_PORT", "8051"))
    base = f"http://{host}:{port}"
    url = f"{base}{path}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        if method == "GET":
            return await client.get(url)
        return await client.post(url, json=json_body)


@app.get("/mcp/commands")
async def _pmoves_mcp_commands():
    # Try common MCP bridge paths to list tools/commands
    for candidate in ("/tools", "/mcp/tools", "/commands"):
        try:
            r = await _proxy_to_mcp(candidate)
            if r.status_code == 200:
                data = r.json()
                # Normalize to {commands:[{name,description?}...]}
                if isinstance(data, dict) and "tools" in data:
                    tools = data["tools"]
                elif isinstance(data, list):
                    tools = data
                else:
                    tools = data.get("commands", []) if isinstance(data, dict) else []
                commands = []
                for t in tools:
                    if isinstance(t, dict):
                        name = t.get("name") or t.get("id") or t.get("tool")
                        desc = t.get("description") or t.get("desc")
                    else:
                        name, desc = str(t), None
                    if name:
                        commands.append({"name": name, "description": desc})
                return {"commands": commands}
        except Exception:
            continue
    raise HTTPException(status_code=502, detail={"error": "mcp_list_unavailable"})


class MCPExecuteRequest(BaseModel):
    tool: str = Field(..., description="Tool name to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict)


@app.post("/mcp/execute")
async def _pmoves_mcp_execute(req: MCPExecuteRequest):
    payload = {"tool": req.tool, "arguments": req.arguments}
    # Try common execution endpoints
    candidates = (
        ("POST", f"/tools/{req.tool}"),
        ("POST", "/execute"),
        ("POST", "/mcp/execute"),
    )
    for method, path in candidates:
        try:
            r = await _proxy_to_mcp(path, method=method, json_body=payload)
            if r.status_code in (200, 201, 202):
                try:
                    return r.json()
                except Exception:
                    return {"ok": True, "raw": r.text}
        except Exception:
            continue
    raise HTTPException(status_code=502, detail={"error": "mcp_execute_failed", "tool": req.tool})


class ManagedSubprocess:
    """Utility to manage long running subprocesses."""

    def __init__(
        self,
        name: str,
        args: list[str],
        env: Optional[dict[str, str]] = None,
        cwd: Optional[Path] = None,
    ) -> None:
        self.name = name
        self.args = args
        self.env = env
        self.cwd = cwd
        self._process: Optional[asyncio.subprocess.Process] = None
        self._monitor_task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        if self._process and self._process.returncode is None:
            LOGGER.debug("%s already running", self.name)
            return

        LOGGER.info("Starting %s subprocess", self.name)
        self._process = await asyncio.create_subprocess_exec(
            *self.args,
            cwd=str(self.cwd) if self.cwd else None,
            env=self.env,
        )
        self._monitor_task = asyncio.create_task(self._monitor())

    async def _monitor(self) -> None:
        if not self._process:
            return

        return_code = await self._process.wait()
        if return_code:
            LOGGER.error("%s exited with code %s", self.name, return_code)
        else:
            LOGGER.info("%s stopped", self.name)
        self._process = None

    async def stop(self) -> None:
        if self._monitor_task:
            self._monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._monitor_task
            self._monitor_task = None

        if self._process and self._process.returncode is None:
            LOGGER.info("Stopping %s subprocess", self.name)
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=10)
            except asyncio.TimeoutError:
                LOGGER.warning("%s did not terminate gracefully; killing", self.name)
                self._process.kill()
                await self._process.wait()

        self._process = None


class UvicornWorker:
    """Run a FastAPI app in-process using Uvicorn on a background task."""

    def __init__(self, name: str, app_import: str, host: str, port: int):
        self.name = name
        self.app_import = app_import
        self.host = host
        self.port = port
        self._task: Optional[asyncio.Task[None]] = None
        self._server: Optional[uvicorn.Server] = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            LOGGER.debug("%s already running", self.name)
            return

        LOGGER.info("Starting %s on %s:%s", self.name, self.host, self.port)
        config = uvicorn.Config(
            self.app_import,
            host=self.host,
            port=self.port,
            log_level="info",
            loop="asyncio",
            lifespan="auto",
        )
        server = uvicorn.Server(config)
        self._server = server

        async def _serve() -> None:
            try:
                await server.serve()
            except Exception:  # pragma: no cover - defensive logging
                LOGGER.exception("%s crashed", self.name)
            finally:
                LOGGER.info("%s stopped", self.name)

        self._task = asyncio.create_task(_serve())

    async def stop(self) -> None:
        if self._server:
            self._server.should_exit = True

        if self._task:
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        self._server = None


def _prepare_agents_app() -> str:
    """Patch the vendored agents server to work in-process and return import path."""

    from server.config.service_discovery import ServiceDiscovery

    service_discovery = ServiceDiscovery()
    api_url = service_discovery.get_service_url("api")

    agents_module = import_module("agents.server")

    import httpx

    async def fetch_credentials_from_server() -> dict[str, str]:
        max_retries = 30
        retry_delay = 10
        target = f"{api_url}/internal/credentials/agents"

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(target, timeout=10.0)
                    response.raise_for_status()
                    credentials = response.json()

                for key, value in credentials.items():
                    if value is not None:
                        os.environ[key] = str(value)
                        agents_module.logger.info("Set credential: %s", key)

                agents_module.AGENT_CREDENTIALS = credentials
                _sync_openai_compat_env()
                agents_module.logger.info(
                    "Successfully fetched %s credentials from server",
                    len(credentials),
                )
                return credentials

            except (httpx.HTTPError, httpx.RequestError) as exc:
                if attempt < max_retries - 1:
                    agents_module.logger.warning(
                        "Failed to fetch credentials (attempt %s/%s): %s",
                        attempt + 1,
                        max_retries,
                        exc,
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    agents_module.logger.error(
                        "Failed to fetch credentials after %s attempts",
                        max_retries,
                    )
                    raise Exception("Could not fetch credentials from server") from exc

    agents_module.fetch_credentials_from_server = fetch_credentials_from_server

    return "agents.server:app"


ARCHON_SUBPROCESS_ENV = {
    **os.environ,
    "PYTHONPATH": _build_pythonpath_env(),
}


MCP_RUNNER = ManagedSubprocess(
    name="archon-mcp",
    args=[
        sys.executable,
        "-m",
        "src.mcp_server.mcp_server",
    ],
    env=ARCHON_SUBPROCESS_ENV,
    cwd=ARCHON_SRC,
)

AGENTS_RUNNER = UvicornWorker(
    name="archon-agents",
    app_import=_prepare_agents_app(),
    host="0.0.0.0",
    port=int(ENV_PORTS["agents_port"]),
)


class ArchonServiceSupervisor:
    """Lifecycle manager for auxiliary Archon services."""

    def __init__(self) -> None:
        self._services = [MCP_RUNNER, AGENTS_RUNNER]

    async def start(self) -> None:
        for service in self._services:
            await service.start()

    async def stop(self) -> None:
        for service in reversed(self._services):
            await service.stop()


SUPERVISOR = ArchonServiceSupervisor()


@asynccontextmanager
async def _supervisor_lifespan(app: FastAPI):
    # Get service configuration for announcement
    port = int(ENV_PORTS["server_port"])
    hostname = os.getenv("HOSTNAME", socket.gethostname())
    slug = os.getenv("SERVICE_SLUG", "archon")
    name = os.getenv("SERVICE_NAME", "PMOVES Archon")
    url = os.getenv("SERVICE_URL") or f"http://{hostname}:{port}"
    health_check = f"{url}/healthz"

    # Announce service on NATS
    if NATS_ANNOUNCE_AVAILABLE:
        try:
            await announce_service(
                nats_url=os.getenv("NATS_URL", "nats://nats:4222"),
                slug=slug,
                name=name,
                url=url,
                health_check=health_check,
                tier=ServiceTier.AGENT,
                port=port,
                metadata={"version": "5.0.0"},
                retry=True,
            )
            LOGGER.info("NATS service announcement published: %s at %s", slug, url)
        except Exception as e:
            LOGGER.warning("Failed to publish NATS service announcement: %s", e)

    await SUPERVISOR.start()
    try:
        yield
    finally:
        await SUPERVISOR.stop()


# Override vendor lifespan entirely to prevent fatal exits when credential bootstrap fails.
app.router.lifespan_context = _supervisor_lifespan


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(ENV_PORTS["server_port"]),
        log_level="info",
    )
