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

from fastapi import Body, Depends, FastAPI, HTTPException
from nats.aio.client import Client as NATS
from pydantic import BaseModel, Field, HttpUrl

try:
    _services_root = Path(__file__).resolve().parents[2]
    if str(_services_root) not in sys.path:
        sys.path.insert(0, str(_services_root))
except Exception:
    pass

from services.common.events import envelope
from .orchestrator import ArchonOrchestrator

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
    """Populate SUPABASE_* defaults so the vendored stack can boot."""

    current = os.environ.get("SUPABASE_URL")
    prefers_internal = False
    if current:
        lowered = current.lower()
        if lowered.startswith("http://host.docker.internal") or lowered.startswith("http://127.0.0.1"):
            prefers_internal = True
        placeholder_host = "your-project.supabase.co"
        if urlparse(current).netloc == placeholder_host:
            current = ""
    if not current or prefers_internal:
        internal = os.environ.get("SUPA_REST_INTERNAL_URL")
        rest = os.environ.get("SUPA_REST_URL") or os.environ.get("SUPABASE_REST_URL")

        def _host_reachable(base: str) -> bool:
            try:
                parsed = urlparse(base)
                host = parsed.hostname
                if not host:
                    return False
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                with socket.create_connection((host, port), timeout=1.5):
                    return True
            except OSError:
                return False

        candidates: list[str] = []
        seen: set[str] = set()
        for candidate in (internal, rest, current, "http://postgrest:3000"):
            if not candidate:
                continue
            base = _strip_rest_suffix(candidate)
            if base in seen:
                continue
            seen.add(base)
            candidates.append(base)

        for base in candidates:
            if _host_reachable(base):
                os.environ["SUPABASE_URL"] = base
                break
        else:
            os.environ.setdefault("SUPABASE_URL", "http://postgrest:3000")

    # Ensure downstream clients find the service role key under the expected alias.
    if os.environ.get("SUPABASE_SERVICE_ROLE_KEY") and not os.environ.get("SUPABASE_KEY"):
        os.environ["SUPABASE_KEY"] = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    os.environ["POSTGRES_HOST"] = os.environ.get("PGHOST", "postgres")


_ensure_supabase_env()


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

    for key in ("SUPA_REST_URL", "SUPA_REST_INTERNAL_URL", "SUPABASE_URL"):
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
    """Import the upstream Archon FastAPI application."""

    try:
        archon_main = import_module("server.main")
    except ModuleNotFoundError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(
            "Unable to import Archon server application from vendor/archon."
        ) from exc

    return archon_main.app


app = _import_archon_app()


@app.get("/healthz")
async def _pmoves_healthcheck():
    return {"status": "ok", "service": "archon"}


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
    await SUPERVISOR.start()
    try:
        yield
    finally:
        await SUPERVISOR.stop()


_existing_lifespan = getattr(app.router, "lifespan_context", None)

if _existing_lifespan is None:
    app.router.lifespan_context = _supervisor_lifespan
else:

    @asynccontextmanager
    async def _composed_lifespan(app: FastAPI):
        async with _existing_lifespan(app):
            async with _supervisor_lifespan(app):
                yield

    app.router.lifespan_context = _composed_lifespan


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(ENV_PORTS["server_port"]),
        log_level="info",
    )
