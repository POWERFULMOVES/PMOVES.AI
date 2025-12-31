from __future__ import annotations

import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, HTTPException, Header, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field, validator

from .config import config_path_from_env, ensure_config, save_config
from .monitor import ChannelMonitor


def _parse_scopes(value: str | None) -> list[str]:
    if not value:
        return []
    tokens = value.replace(",", " ").split()
    return [token for token in tokens if token]

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
GOOGLE_CLIENT_ID = os.getenv("CHANNEL_MONITOR_GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("CHANNEL_MONITOR_GOOGLE_REDIRECT_URI")
GOOGLE_SCOPES = _parse_scopes(os.getenv("CHANNEL_MONITOR_GOOGLE_SCOPES"))

monitor = ChannelMonitor(
    config_path=CONFIG_PATH,
    queue_url=QUEUE_URL,
    database_url=DATABASE_URL,
    namespace_default=DEFAULT_NAMESPACE,
    google_client_id=GOOGLE_CLIENT_ID,
    google_client_secret=GOOGLE_CLIENT_SECRET,
    google_redirect_uri=GOOGLE_REDIRECT_URI,
    google_scopes=GOOGLE_SCOPES or None,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Channel Monitor application lifespan."""
    # Startup
    await monitor.start()
    app.state.monitor = monitor
    # Ensure metrics counters exist
    _ = CHANNEL_CHECKS_TOTAL.labels(kind="startup").inc(0)
    _ = STATUS_UPDATES_TOTAL.labels(result="noop").inc(0)
    yield
    # Shutdown
    await monitor.shutdown()


app = FastAPI(
    title="PMOVES Channel Monitor",
    version="0.1.0",
    lifespan=lifespan,
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
    channel_metadata_fields: list[str] | None = Field(
        None,
        description="Override the fields captured in channel metadata (defaults from global settings)",
    )
    video_metadata_fields: list[str] | None = Field(
        None,
        description="Override the fields captured in per-video metadata (defaults from global settings)",
    )


class UpdateStatusRequest(BaseModel):
    video_id: str
    status: str
    error: str | None = None
    metadata: Dict[str, Any] | None = None


class OAuthTokenRequest(BaseModel):
    user_id: str = Field(..., description="Supabase user UUID")
    provider: str = Field("youtube", description="OAuth provider key")
    refresh_token: str = Field(..., description="OAuth refresh token")
    scope: List[str] = Field(default_factory=list)
    expires_at: datetime | None = Field(None, description="Token expiry timestamp (UTC)")
    expires_in: int | None = Field(None, description="Seconds until token expiry (if expires_at missing)")

    @validator("scope", pre=True)
    def _normalize_scope(cls, value):  # type: ignore[no-untyped-def]
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [token for token in value.replace(",", " ").split() if token]
        if isinstance(value, list):
            return [token for token in value if isinstance(token, str)]
        raise ValueError("scope must be a string or list of strings")


class UserSourceRequest(BaseModel):
    user_id: str = Field(..., description="Supabase user UUID")
    provider: str = Field("youtube", description="Media platform provider")
    source_type: str = Field(..., description="Type of source (channel, playlist, likes, user)")
    source_identifier: str | None = Field(None, description="Stable identifier (channel ID, playlist ID)")
    source_url: str | None = Field(None, description="Canonical source URL")
    namespace: str | None = Field(None, description="Namespace for ingestion")
    tags: List[str] | None = None
    auto_process: bool = True
    check_interval_minutes: int | None = Field(None, ge=1)
    filters: Dict[str, Any] | None = None
    yt_options: Dict[str, Any] | None = None
    token_id: str | None = Field(None, description="Linked OAuth token ID")
    status: str = Field("active", description="Source status")


async def require_secret(token: str | None = Header(default=None, alias="X-Channel-Monitor-Token")) -> None:
    if STATUS_SECRET and token != STATUS_SECRET:
        raise HTTPException(status_code=401, detail="invalid or missing token")
    return None


def get_monitor(request: Request) -> ChannelMonitor:
    instance = getattr(request.app.state, "monitor", None)
    if instance is None:
        raise HTTPException(status_code=503, detail="monitor not initialized")
    return instance


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {
        "status": "ok",
        "queue_url": QUEUE_URL,
        "database_url": DATABASE_URL,
        "channels": monitor.channel_count(),
    }


@app.get("/api/monitor/stats")
async def stats():
    return await monitor.get_stats()


@app.get("/api/monitor/channels")
async def channels():
    return monitor.list_channels()


@app.post("/api/monitor/check-now")
async def trigger_check(monitor: ChannelMonitor = Depends(get_monitor)):
    await monitor.check_all_channels()
    CHANNEL_CHECKS_TOTAL.labels(kind="manual").inc()
    return {"status": "ok"}


@app.post("/api/monitor/channel")
async def add_channel(payload: AddChannelRequest, monitor: ChannelMonitor = Depends(get_monitor)):
    try:
        new_channel = await monitor.add_channel(payload.dict())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    CONFIG.setdefault("channels", []).append(new_channel)
    save_config(CONFIG_PATH, CONFIG)
    return {"status": "ok", "channel": new_channel}


@app.post("/api/monitor/status")
async def update_status(
    payload: UpdateStatusRequest,
    _: None = Depends(require_secret),
    monitor: ChannelMonitor = Depends(get_monitor),
):
    try:
        updated = await monitor.apply_status_update(
            payload.video_id,
            payload.status,
            error=payload.error,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    STATUS_UPDATES_TOTAL.labels(result="success").inc()
    return {"status": "ok", "updated": updated}


# Lightweight health probe for monitoring (does not require secret)
@app.get("/api/monitor/status")
async def status_probe() -> Dict[str, Any]:
    try:
        # Return a minimal payload quickly; full stats remain at /api/monitor/stats
        return {
            "status": "ok",
            "service": "channel-monitor",
        }
    except Exception as exc:  # pragma: no cover
        # If anything unexpected occurs, surface a 503 for blackbox
        raise HTTPException(status_code=503, detail=str(exc))


# ---- Prometheus metrics ----
CHANNEL_CHECKS_TOTAL = Counter(
    "channel_monitor_checks_total",
    "Total number of channel checks triggered",
    labelnames=("kind",),
)

STATUS_UPDATES_TOTAL = Counter(
    "channel_monitor_status_updates_total",
    "Total number of status updates received",
    labelnames=("result",),
)


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    data = generate_latest()  # type: ignore[arg-type]
    return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)


@app.post("/api/oauth/google/token")
async def upsert_google_token(
    payload: OAuthTokenRequest,
    monitor: ChannelMonitor = Depends(get_monitor),
):
    token_id = await monitor.upsert_user_token(payload.dict())
    return {"status": "ok", "token_id": str(token_id)}


@app.post("/api/monitor/user-source")
async def register_user_source(
    payload: UserSourceRequest,
    monitor: ChannelMonitor = Depends(get_monitor),
):
    source = await monitor.upsert_user_source(payload.dict())
    return {"status": "ok", "source": source}


@app.get("/api/monitor/user-sources")
async def list_user_sources(monitor: ChannelMonitor = Depends(get_monitor)):
    sources = await monitor.list_user_sources()
    return {"status": "ok", "sources": sources}
