from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shlex
import signal
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httpx
from fastapi import Body, Depends, FastAPI, HTTPException, Path as FPath, Query
from pydantic import BaseModel, Field

from services.agent_zero.controller import AgentZeroController, ControllerSettings

import mcp_server

logger = logging.getLogger("pmoves.agent_zero.service")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass
class AgentZeroRuntimeConfig:
    """Configuration container for the Agent Zero runtime wrapper."""

    root: Path = field(
        default_factory=lambda: Path(
            os.environ.get("AGENT_ZERO_ROOT", "/opt/agent-zero")
        )
    )
    entrypoint: str = field(
        default_factory=lambda: os.environ.get("AGENT_ZERO_ENTRYPOINT", "run_ui.py")
    )
    python_executable: str = field(
        default_factory=lambda: os.environ.get("AGENT_ZERO_PYTHON", sys.executable)
    )
    extra_args: List[str] = field(default_factory=list)
    api_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "AGENT_ZERO_API_BASE", "http://127.0.0.1:50001"
        )
    )
    api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("AGENT_ZERO_API_KEY")
    )
    health_path: str = field(
        default_factory=lambda: os.environ.get("AGENT_ZERO_HEALTH_PATH", "/health")
    )
    startup_timeout: float = field(
        default_factory=lambda: float(
            os.environ.get("AGENT_ZERO_STARTUP_TIMEOUT", "180")
        )
    )
    health_timeout: float = field(
        default_factory=lambda: float(os.environ.get("AGENT_ZERO_HEALTH_TIMEOUT", "5"))
    )
    message_path: str = field(
        default_factory=lambda: os.environ.get(
            "AGENT_ZERO_MESSAGE_PATH", "/api_message"
        )
    )
    log_path: str = field(
        default_factory=lambda: os.environ.get("AGENT_ZERO_LOG_PATH", "/api_log_get")
    )
    memory_list_path: str = field(
        default_factory=lambda: os.environ.get(
            "AGENT_ZERO_MEMORY_LIST_PATH", "/api/memory/list"
        )
    )
    memory_create_path: str = field(
        default_factory=lambda: os.environ.get(
            "AGENT_ZERO_MEMORY_CREATE_PATH", "/api/memory"
        )
    )
    memory_detail_path: str = field(
        default_factory=lambda: os.environ.get(
            "AGENT_ZERO_MEMORY_DETAIL_PATH", "/api/memory/{memory_id}"
        )
    )
    capture_subprocess_output: bool = field(
        default_factory=lambda: _env_bool("AGENT_ZERO_CAPTURE_OUTPUT", False)
    )

    def __post_init__(self) -> None:
        extra = os.environ.get("AGENT_ZERO_EXTRA_ARGS")
        if extra:
            self.extra_args = shlex.split(extra)

    @property
    def resolved_entrypoint(self) -> Path:
        """Return the resolved entrypoint path, checking common fallbacks."""

        candidates: Iterable[Path] = (
            Path(self.entrypoint),
            self.root / self.entrypoint,
            self.root / "run_ui.py",
            self.root / "agent.py",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(
            f"Unable to locate Agent Zero entrypoint. Looked for {self.entrypoint!r} "
            f"within {self.root}"
        )

    @property
    def command(self) -> List[str]:
        return [self.python_executable, str(self.resolved_entrypoint), *self.extra_args]

    @property
    def runtime_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        # Allow callers to forward prefixed environment variables to the runtime.
        for key, value in list(env.items()):
            if key.startswith("AGENT_ZERO_RUNTIME_"):
                runtime_key = key.replace("AGENT_ZERO_RUNTIME_", "", 1)
                env[runtime_key] = value
        return env


class AgentZeroServiceConfig(BaseModel):
    """Configuration exposed via the public Agent Zero API."""

    port: int = Field(default=8080, description="Port the FastAPI service listens on")
    nats_url: str = Field(
        default="nats://nats:4222", description="NATS connection string"
    )
    geometry_gateway_url: str = Field(
        default="http://localhost:8087",
        description="Base URL for the geometry gateway runtime",
    )
    youtube_ingest_url: str = Field(
        default="http://localhost:8077",
        description="Base URL for the YouTube ingest runtime",
    )
    render_webhook_url: str = Field(
        default="http://localhost:8085",
        description="Webhook endpoint for ComfyUI renders",
    )
    agent_form: str = Field(
        default="POWERFULMOVES", description="Default MCP form name"
    )
    agent_forms_dir: str = Field(
        default="configs/agents/forms",
        description="Directory containing Agent Zero YAML form definitions",
    )
    knowledge_base_dir: str = Field(
        default="runtime/knowledge",
        description="Local directory for Agent Zero knowledge base artifacts",
    )
    mcp_runtime_dir: str = Field(
        default="runtime/mcp",
        description="Directory used by MCP runtime shims (logs, pipes, sockets)",
    )


def load_service_config() -> AgentZeroServiceConfig:
    return AgentZeroServiceConfig(
        port=int(os.environ.get("PORT", 8080)),
        nats_url=os.environ.get("NATS_URL", "nats://nats:4222"),
        geometry_gateway_url=os.environ.get(
            "HIRAG_URL", os.environ.get("GATEWAY_URL", "http://localhost:8087")
        ),
        youtube_ingest_url=os.environ.get("YT_URL", "http://localhost:8077"),
        render_webhook_url=os.environ.get(
            "RENDER_WEBHOOK_URL", "http://localhost:8085"
        ),
        agent_form=os.environ.get("AGENT_FORM", "POWERFULMOVES"),
        agent_forms_dir=os.environ.get("AGENT_FORMS_DIR", "configs/agents/forms"),
        knowledge_base_dir=os.environ.get(
            "AGENT_KNOWLEDGE_BASE_DIR", "runtime/knowledge"
        ),
        mcp_runtime_dir=os.environ.get("AGENT_MCP_RUNTIME_DIR", "runtime/mcp"),
    )


# ---------------------------------------------------------------------------
# Runtime client
# ---------------------------------------------------------------------------


class AgentZeroRequestError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class AgentZeroClient:
    def __init__(self, config: AgentZeroRuntimeConfig) -> None:
        self._config = config

    @property
    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._config.api_key:
            headers["X-API-KEY"] = self._config.api_key
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        url = self._config.api_base_url.rstrip("/")
        request_path = path
        async with httpx.AsyncClient(base_url=url, timeout=timeout or 60.0) as client:
            response = await client.request(
                method,
                request_path,
                params=params,
                json=json_body,
                headers=self._headers,
            )
        if response.status_code >= 400:
            message = response.text
            try:
                payload = response.json()
            except Exception:  # pragma: no cover - best effort to decode JSON
                payload = None
            if isinstance(payload, dict) and payload.get("error"):
                message = str(payload.get("error"))
            raise AgentZeroRequestError(response.status_code, message)
        if "application/json" in response.headers.get("content-type", ""):
            return response.json()
        return response.text

    async def health(self) -> Dict[str, Any]:
        try:
            result = await self._request(
                "GET",
                self._config.health_path,
                timeout=self._config.health_timeout,
            )
            if isinstance(result, dict):
                return result
            return {"status": "ok", "raw": result}
        except (
            AgentZeroRequestError
        ) as exc:  # pragma: no cover - runtime might not be ready
            logger.debug("Agent Zero health check failed: %s", exc)
            raise

    async def send_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = await self._request(
            "POST", self._config.message_path, json_body=payload
        )
        if not isinstance(result, dict):
            raise AgentZeroRequestError(
                500, "Unexpected response from Agent Zero message endpoint"
            )
        return result

    async def fetch_log(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = await self._request("POST", self._config.log_path, json_body=payload)
        if not isinstance(result, dict):
            raise AgentZeroRequestError(
                500, "Unexpected response from Agent Zero log endpoint"
            )
        return result

    async def list_memories(self, params: Dict[str, Any]) -> Any:
        return await self._request("GET", self._config.memory_list_path, params=params)

    async def create_memory(self, payload: Dict[str, Any]) -> Any:
        return await self._request(
            "POST", self._config.memory_create_path, json_body=payload
        )

    async def get_memory(self, memory_id: str) -> Any:
        path = self._config.memory_detail_path.format(memory_id=memory_id)
        return await self._request("GET", path)

    async def update_memory(self, memory_id: str, payload: Dict[str, Any]) -> Any:
        path = self._config.memory_detail_path.format(memory_id=memory_id)
        return await self._request("PUT", path, json_body=payload)

    async def delete_memory(self, memory_id: str) -> Any:
        path = self._config.memory_detail_path.format(memory_id=memory_id)
        return await self._request("DELETE", path)


# ---------------------------------------------------------------------------
# Process manager
# ---------------------------------------------------------------------------


class AgentZeroProcessManager:
    """Manage the lifecycle of the Agent Zero subprocess."""

    def __init__(self, config: AgentZeroRuntimeConfig, client: AgentZeroClient) -> None:
        self._config = config
        self._client = client
        self._process: Optional[asyncio.subprocess.Process] = None
        self._lock = asyncio.Lock()
        self._watchdog_task: Optional[asyncio.Task[None]] = None
        self._ready = asyncio.Event()
        self._stopping = False
        self._last_returncode: Optional[int] = None

    @property
    def command(self) -> List[str]:
        return self._config.command

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def last_returncode(self) -> Optional[int]:
        return self._last_returncode

    async def start(self) -> None:
        async with self._lock:
            if self.is_running:
                return
            entrypoint = self._config.resolved_entrypoint
            if not entrypoint.exists():
                raise FileNotFoundError(
                    f"Agent Zero entrypoint not found at {entrypoint}"
                )
            logger.info("Starting Agent Zero runtime: %s", " ".join(self.command))
            stdout = (
                asyncio.subprocess.PIPE
                if self._config.capture_subprocess_output
                else None
            )
            stderr = (
                asyncio.subprocess.PIPE
                if self._config.capture_subprocess_output
                else None
            )
            self._process = await asyncio.create_subprocess_exec(
                *self.command,
                cwd=str(entrypoint.parent),
                env=self._config.runtime_env,
                stdout=stdout,
                stderr=stderr,
            )
            self._ready.clear()
            self._stopping = False
            self._watchdog_task = asyncio.create_task(
                self._watchdog(), name="agent-zero-watchdog"
            )
        await self._wait_until_ready()

    async def _wait_until_ready(self) -> None:
        deadline = asyncio.get_event_loop().time() + self._config.startup_timeout
        while asyncio.get_event_loop().time() < deadline:
            if self._stopping:
                return
            if self._process and self._process.returncode is not None:
                self._last_returncode = self._process.returncode
                raise RuntimeError(
                    f"Agent Zero process exited prematurely with code {self._process.returncode}"
                )
            try:
                await self._client.health()
            except AgentZeroRequestError:
                await asyncio.sleep(1)
                continue
            else:
                self._ready.set()
                logger.info("Agent Zero runtime is ready")
                return
        raise TimeoutError("Timed out waiting for Agent Zero runtime to become healthy")

    async def stop(self) -> None:
        async with self._lock:
            self._stopping = True
            process = self._process
            if not process:
                return
            if process.returncode is None:
                logger.info("Stopping Agent Zero runtime (pid=%s)", process.pid)
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=15)
                except asyncio.TimeoutError:
                    logger.warning("Agent Zero runtime did not exit in time, killing")
                    process.kill()
                    await process.wait()
            self._last_returncode = process.returncode
            self._process = None
            self._ready.clear()
            if self._watchdog_task:
                self._watchdog_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._watchdog_task
                self._watchdog_task = None

    async def _watchdog(self) -> None:
        assert self._process is not None
        process = self._process
        try:
            await process.wait()
            self._last_returncode = process.returncode
            if not self._stopping:
                logger.error(
                    "Agent Zero runtime exited unexpectedly with code %s",
                    process.returncode,
                )
        except asyncio.CancelledError:  # pragma: no cover - normal shutdown path
            raise

    async def ensure_running(self) -> None:
        if not self.is_running:
            await self.start()
        elif not self._ready.is_set():
            await self._wait_until_ready()


# ---------------------------------------------------------------------------
# FastAPI schemas
# ---------------------------------------------------------------------------


class Attachment(BaseModel):
    filename: str
    base64: str


class SessionRequest(BaseModel):
    message: str = Field(..., description="Prompt or instruction to send to Agent Zero")
    context_id: Optional[str] = Field(
        None, description="Existing conversation identifier"
    )
    attachments: List[Attachment] = Field(default_factory=list)
    lifetime_hours: Optional[float] = Field(
        None, description="How long Agent Zero should retain the session"
    )


class TaskSubmissionRequest(BaseModel):
    message: str
    attachments: List[Attachment] = Field(default_factory=list)
    lifetime_hours: Optional[float] = None
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional task metadata"
    )


class MemoryPayload(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)


class EventPublishRequest(BaseModel):
    topic: str = Field(..., description="NATS topic to publish to")
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Event payload body"
    )
    correlation_id: Optional[str] = Field(
        default=None, description="Correlation identifier to include in the envelope"
    )
    parent_id: Optional[str] = Field(
        default=None, description="Parent envelope identifier"
    )
    source: Optional[str] = Field(
        default=None,
        description="Override the source field on the published envelope",
    )


class MCPExecuteRequest(BaseModel):
    cmd: str = Field(..., description="MCP command name")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Arguments for the command"
    )


class MCPExecuteResponse(BaseModel):
    cmd: str
    result: Dict[str, Any]


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------


service_config = load_service_config()
runtime_config = AgentZeroRuntimeConfig()
client = AgentZeroClient(runtime_config)
process_manager = AgentZeroProcessManager(runtime_config, client)
app = FastAPI(title="Agent Zero Supervisor")

controller_settings = ControllerSettings(nats_url=service_config.nats_url)
event_controller = AgentZeroController(controller_settings)
_controller_task: Optional[asyncio.Task[None]] = None
_controller_shutdown = asyncio.Event()
_controller_ready = asyncio.Event()


def get_service_config() -> AgentZeroServiceConfig:
    return service_config


async def ensure_runtime_running() -> None:
    await process_manager.ensure_running()


async def _controller_connect_loop() -> None:
    backoff = 1.0
    while not _controller_shutdown.is_set():
        try:
            await event_controller.start()
        except Exception:  # pragma: no cover - connectivity issues
            _controller_ready.clear()
            logger.exception("Failed to start Agent Zero controller")
            try:
                await asyncio.wait_for(_controller_shutdown.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                backoff = min(backoff * 2, 30.0)
            continue
        else:
            _controller_ready.set()
            try:
                await _controller_shutdown.wait()
            finally:
                _controller_ready.clear()
            break


@app.on_event("startup")
async def on_startup() -> None:
    await process_manager.start()
    global _controller_task
    _controller_shutdown.clear()
    _controller_task = asyncio.create_task(
        _controller_connect_loop(), name="agent-zero-controller-connect"
    )
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(
                sig, lambda s=sig: asyncio.create_task(process_manager.stop())
            )
        except NotImplementedError:  # pragma: no cover - platform specific
            logger.warning("Signal handlers not supported on this platform")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await process_manager.stop()
    _controller_shutdown.set()
    global _controller_task
    if _controller_task:
        with contextlib.suppress(asyncio.CancelledError):
            await _controller_task
        _controller_task = None
    if event_controller.is_started:
        with contextlib.suppress(Exception):
            await event_controller.stop()


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    running = process_manager.is_running
    status = "ok" if running else "stopped"
    detail: Dict[str, Any] = {
        "status": status,
        "command": process_manager.command,
        "pid": getattr(process_manager._process, "pid", None),
        "last_returncode": process_manager.last_returncode,
    }
    detail["nats"] = {
        "url": service_config.nats_url,
        "connected": event_controller.is_connected,
        "controller_started": event_controller.is_started,
        "subjects": list(controller_settings.subjects),
        "stream": controller_settings.stream_name,
    }
    if event_controller.is_started:
        detail["nats"]["metrics"] = event_controller.metrics
    if running:
        try:
            runtime_health = await client.health()
            detail["runtime"] = runtime_health
        except AgentZeroRequestError as exc:
            detail["runtime"] = {"status": "error", "detail": str(exc)}
    return detail


@app.get("/config/environment", response_model=AgentZeroServiceConfig)
def get_environment_endpoint() -> AgentZeroServiceConfig:
    return get_service_config()


@app.get("/mcp/commands")
def list_mcp_commands(
    config: AgentZeroServiceConfig = Depends(get_service_config),
) -> Dict[str, Any]:
    return {
        "default_form": config.agent_form,
        "forms_dir": config.agent_forms_dir,
        "runtime": {
            "knowledge_base_dir": config.knowledge_base_dir,
            "mcp_runtime_dir": config.mcp_runtime_dir,
        },
        "commands": mcp_server.list_commands(),
    }


async def _execute_command(cmd: str, args: Dict[str, Any]) -> Dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, mcp_server.execute_command, cmd, args)


@app.post("/mcp/execute", response_model=MCPExecuteResponse)
async def execute_mcp_command(request: MCPExecuteRequest) -> MCPExecuteResponse:
    if request.cmd not in mcp_server.COMMAND_REGISTRY:
        raise HTTPException(
            status_code=404, detail=f"Unknown MCP command: {request.cmd}"
        )
    try:
        result = await _execute_command(request.cmd, request.arguments)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MCPExecuteResponse(cmd=request.cmd, result=result)


@app.post("/events/publish", response_model=Dict[str, str])
async def events_publish(body: EventPublishRequest) -> Dict[str, str]:
    if not (_controller_ready.is_set() and event_controller.is_connected):
        raise HTTPException(status_code=503, detail="NATS controller not ready")
    env = await event_controller.publish(
        body.topic,
        body.payload,
        correlation_id=body.correlation_id,
        parent_id=body.parent_id,
        source=body.source or "agent-zero",
    )
    response: Dict[str, str] = {"published": body.topic}
    envelope_id = env.get("id")
    if envelope_id:
        response["id"] = envelope_id
    return response


@app.post("/sessions")
async def send_session_message(
    request: SessionRequest, _: None = Depends(ensure_runtime_running)
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "message": request.message,
    }
    if request.context_id:
        payload["context_id"] = request.context_id
    if request.attachments:
        payload["attachments"] = [
            attachment.dict() for attachment in request.attachments
        ]
    if request.lifetime_hours is not None:
        payload["lifetime_hours"] = request.lifetime_hours
    try:
        return await client.send_message(payload)
    except AgentZeroRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.post("/tasks")
async def submit_task(
    request: TaskSubmissionRequest, _: None = Depends(ensure_runtime_running)
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "message": request.message,
    }
    if request.attachments:
        payload["attachments"] = [
            attachment.dict() for attachment in request.attachments
        ]
    if request.lifetime_hours is not None:
        payload["lifetime_hours"] = request.lifetime_hours
    payload.update(request.metadata)
    try:
        return await client.send_message(payload)
    except AgentZeroRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.get("/jobs/{context_id}")
async def job_status(
    context_id: str = FPath(..., description="Agent Zero context identifier"),
    length: int = Query(
        100, ge=1, le=1000, description="Number of recent log entries to retrieve"
    ),
    _: None = Depends(ensure_runtime_running),
) -> Dict[str, Any]:
    payload = {"context_id": context_id, "length": length}
    try:
        return await client.fetch_log(payload)
    except AgentZeroRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.get("/memory")
async def list_memories(
    query: Optional[str] = Query(None, description="Optional memory query"),
    limit: Optional[int] = Query(None, ge=1, description="Limit number of results"),
    offset: Optional[int] = Query(None, ge=0, description="Offset for pagination"),
    _: None = Depends(ensure_runtime_running),
) -> Any:
    params: Dict[str, Any] = {}
    if query is not None:
        params["query"] = query
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    try:
        return await client.list_memories(params)
    except AgentZeroRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.get("/memory/{memory_id}")
async def get_memory(
    memory_id: str,
    _: None = Depends(ensure_runtime_running),
) -> Any:
    try:
        return await client.get_memory(memory_id)
    except AgentZeroRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.post("/memory")
async def create_memory(
    body: MemoryPayload = Body(...),
    _: None = Depends(ensure_runtime_running),
) -> Any:
    try:
        return await client.create_memory(body.payload)
    except AgentZeroRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.put("/memory/{memory_id}")
async def update_memory(
    memory_id: str,
    body: MemoryPayload = Body(...),
    _: None = Depends(ensure_runtime_running),
) -> Any:
    try:
        return await client.update_memory(memory_id, body.payload)
    except AgentZeroRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.delete("/memory/{memory_id}")
async def delete_memory(
    memory_id: str,
    _: None = Depends(ensure_runtime_running),
) -> Any:
    try:
        return await client.delete_memory(memory_id)
    except AgentZeroRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=service_config.port)
