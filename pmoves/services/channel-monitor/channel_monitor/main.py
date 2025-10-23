from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, Header
from pydantic import BaseModel, Field

from .config import config_path_from_env, ensure_config, save_config
from .monitor import ChannelMonitor, lifespan_monitor

logging.basicConfig(level=os.getenv("CHANNEL_MONITOR_LOG_LEVEL", "INFO"))
LOGGER = logging.getLogger("channel_monitor")

CONFIG_PATH = config_path_from_env()
CONFIG = ensure_config(CONFIG_PATH)

QUEUE_URL = os.getenv("CHANNEL_MONITOR_QUEUE_URL", "http://pmoves-yt:8077/yt/ingest")
DATABASE_URL = os.getenv(
    "CHANNEL_MONITOR_DATABASE_URL", "postgresql://pmoves:pmoves@postgres:5432/pmoves"
)
DEFAULT_NAMESPACE = os.getenv("CHANNEL_MONITOR_NAMESPACE", "pmoves")
STATUS_SECRET = os.getenv("CHANNEL_MONITOR_SECRET")

monitor = ChannelMonitor(
    config_path=CONFIG_PATH,
    queue_url=QUEUE_URL,
    database_url=DATABASE_URL,
    namespace_default=DEFAULT_NAMESPACE,
)

app = FastAPI(
    title="PMOVES Channel Monitor",
    version="0.1.0",
    lifespan=lambda app: lifespan_monitor(monitor),
)


class AddChannelRequest(BaseModel):
    channel_id: str = Field(..., description="YouTube channel ID")
    channel_name: str | None = Field(None, description="Friendly name for the channel")
    auto_process: bool = True
    check_interval_minutes: int = Field(60, ge=1)
    priority: int = 0
    namespace: str | None = None
    tags: list[str] | None = None
    filters: Dict[str, Any] | None = None
    enabled: bool = True


class UpdateStatusRequest(BaseModel):
    video_id: str
    status: str
    error: str | None = None
    metadata: Dict[str, Any] | None = None


async def require_secret(token: str | None = Header(default=None, alias="X-Channel-Monitor-Token")) -> None:
    if STATUS_SECRET and token != STATUS_SECRET:
        raise HTTPException(status_code=401, detail="invalid or missing token")
    return None


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {
        "status": "ok",
        "queue_url": QUEUE_URL,
        "database_url": DATABASE_URL,
        "channels": len(CONFIG.get("channels", [])),
    }


@app.get("/api/monitor/stats")
async def stats():
    return await monitor.get_stats()


@app.get("/api/monitor/channels")
async def channels():
    return CONFIG.get("channels", [])


@app.post("/api/monitor/check-now")
async def trigger_check():
    await monitor.check_all_channels()
    return {"status": "ok"}


@app.post("/api/monitor/channel")
async def add_channel(payload: AddChannelRequest):
    try:
        new_channel = await monitor.add_channel(payload.dict())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    CONFIG.setdefault("channels", []).append(new_channel)
    save_config(CONFIG_PATH, CONFIG)
    return {"status": "ok", "channel": new_channel}


@app.post("/api/monitor/status")
async def update_status(payload: UpdateStatusRequest, _: None = Depends(require_secret)):
    try:
        updated = await monitor.apply_status_update(
            payload.video_id,
            payload.status,
            error=payload.error,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "updated": updated}
