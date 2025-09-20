import asyncio
import json
import os
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from nats.aio.client import Client as NATS

from services.common.events import envelope

import mcp_server


class AgentZeroConfig(BaseModel):
    port: int = Field(default=8080, description="Port the FastAPI service listens on")
    nats_url: str = Field(default="nats://nats:4222", description="NATS connection string")
    geometry_gateway_url: str = Field(
        default="http://localhost:8087",
        description="Base URL for the geometry gateway runtime",
    )
    youtube_ingest_url: str = Field(
        default="http://localhost:8077", description="Base URL for the YouTube ingest runtime"
    )
    render_webhook_url: str = Field(
        default="http://localhost:8085", description="Webhook endpoint for ComfyUI renders"
    )
    agent_form: str = Field(default="POWERFULMOVES", description="Default MCP form name")
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


def load_config() -> AgentZeroConfig:
    return AgentZeroConfig(
        port=int(os.environ.get("PORT", 8080)),
        nats_url=os.environ.get("NATS_URL", "nats://nats:4222"),
        geometry_gateway_url=os.environ.get("HIRAG_URL", os.environ.get("GATEWAY_URL", "http://localhost:8087")),
        youtube_ingest_url=os.environ.get("YT_URL", "http://localhost:8077"),
        render_webhook_url=os.environ.get("RENDER_WEBHOOK_URL", "http://localhost:8085"),
        agent_form=os.environ.get("AGENT_FORM", "POWERFULMOVES"),
        agent_forms_dir=os.environ.get("AGENT_FORMS_DIR", "configs/agents/forms"),
        knowledge_base_dir=os.environ.get("AGENT_KNOWLEDGE_BASE_DIR", "runtime/knowledge"),
        mcp_runtime_dir=os.environ.get("AGENT_MCP_RUNTIME_DIR", "runtime/mcp"),
    )


app = FastAPI(
    title="Agent-Zero (PMOVES v5)",
    description="Runtime API for publishing events and invoking MCP-compatible Agent Zero helpers.",
)

_nc: Optional[NATS] = None


class EventPublishRequest(BaseModel):
    topic: str = Field(..., description="NATS topic to publish to")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event payload body")


class MCPExecuteRequest(BaseModel):
    cmd: str = Field(..., description="MCP command name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the command")


class MCPExecuteResponse(BaseModel):
    cmd: str
    result: Dict[str, Any]


@app.get("/healthz", tags=["system"])
def healthz() -> Dict[str, str]:
    return {"status": "ok", "service": "agent-zero"}


@app.get("/config/environment", response_model=AgentZeroConfig, tags=["configuration"])
def get_environment(config: AgentZeroConfig = Depends(load_config)) -> AgentZeroConfig:
    return config


@app.get("/mcp/commands", tags=["mcp"])
def list_mcp_commands(config: AgentZeroConfig = Depends(load_config)) -> Dict[str, Any]:
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


@app.post("/mcp/execute", response_model=MCPExecuteResponse, tags=["mcp"])
async def execute_mcp_command(request: MCPExecuteRequest) -> MCPExecuteResponse:
    if request.cmd not in mcp_server.COMMAND_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown MCP command: {request.cmd}")
    try:
        result = await _execute_command(request.cmd, request.arguments)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MCPExecuteResponse(cmd=request.cmd, result=result)


@app.post("/events/publish", response_model=Dict[str, str], tags=["events"])
async def events_publish(body: EventPublishRequest) -> Dict[str, str]:
    topic = body.topic
    payload = body.payload
    msg = envelope(topic, payload, source="agent-zero")
    if not _nc or not _nc.is_connected:
        raise HTTPException(status_code=503, detail="NATS connection not ready")
    await _nc.publish(topic.encode(), json.dumps(msg).encode())
    return {"published": topic}


async def nats_listener(nats_url: str):
    global _nc
    _nc = NATS()
    await _nc.connect(servers=[nats_url])


@app.on_event("startup")
async def startup_event():
    config = load_config()
    asyncio.create_task(nats_listener(config.nats_url))


@app.on_event("shutdown")
async def shutdown_event():
    if _nc and _nc.is_connected:
        await _nc.drain()


if __name__ == "__main__":
    import uvicorn

    config = load_config()
    uvicorn.run(app, host="0.0.0.0", port=config.port)
