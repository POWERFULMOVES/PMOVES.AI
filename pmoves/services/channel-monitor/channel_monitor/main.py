"""PMOVES Channel Monitor - External Content Watcher Service.

This FastAPI application monitors YouTube channels, playlists, and user sources
for new content and triggers ingestion workflows when updates are detected.

The service integrates with:
- PMOVES.YT (port 8077) for video ingestion
- PostgreSQL for persistent state management
- Prometheus for metrics collection
- OAuth2 providers for authenticated channel access

Key Features:
- Multi-tenant channel monitoring with namespace support
- OAuth token management for user-specific sources
- Configurable check intervals and priority-based processing
- Metadata field filtering and customization
- Real-time status updates via webhook callbacks

Environment Variables:
    CHANNEL_MONITOR_LOG_LEVEL: Logging level (default: INFO)
    CHANNEL_MONITOR_QUEUE_URL: Ingestion endpoint URL
    CHANNEL_MONITOR_DATABASE_URL: PostgreSQL connection string
    CHANNEL_MONITOR_NAMESPACE: Default namespace for sources
    CHANNEL_MONITOR_SECRET: Auth token for protected endpoints
    CHANNEL_MONITOR_GOOGLE_CLIENT_ID: Google OAuth client ID
    CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET: Google OAuth client secret
    CHANNEL_MONITOR_GOOGLE_REDIRECT_URI: OAuth redirect URI
    CHANNEL_MONITOR_GOOGLE_SCOPES: Comma-separated OAuth scopes
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
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
    """Parse OAuth scopes from a comma or space-separated string.

    Args:
        value: Comma or space-separated OAuth scopes, or None.

    Returns:
        List of non-empty scope tokens. Returns empty list if value is None or empty.

    Examples:
        >>> _parse_scopes("scope1,scope2 scope3")
        ['scope1', 'scope2', 'scope3']
        >>> _parse_scopes(None)
        []
    """
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
    """Manage Channel Monitor application lifespan.

    Handles startup and shutdown events for the FastAPI application.
    On startup, initializes the channel monitor and ensures metrics
    counters are properly initialized. On shutdown, gracefully closes
    database connections and stops background tasks.

    Args:
        app: FastAPI application instance.

    Yields:
        None. Control is yielded back to FastAPI for the application lifetime.

    Notes:
        - Stores monitor instance in app.state.monitor for dependency injection
        - Initializes Prometheus metric counters with zero values to ensure
          all label combinations exist before first use
    """
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
    """Request model for adding a new channel to monitor.

    Attributes:
        channel_id: YouTube channel ID to monitor.
        channel_name: Optional friendly name for the channel.
        auto_process: Whether to automatically process new videos. Default is True.
        check_interval_minutes: Interval in minutes between checks. Must be >= 1. Default is 60.
        priority: Processing priority (higher values = higher priority). Default is 0.
        namespace: Namespace for multi-tenant isolation. Uses default if None.
        tags: List of tags for categorization and filtering.
        filters: Additional filters for video processing (e.g., duration, title patterns).
        enabled: Whether monitoring is enabled for this channel. Default is True.
        channel_metadata_fields: Override default channel metadata fields captured.
        video_metadata_fields: Override default per-video metadata fields captured.

    Notes:
        Metadata field overrides take precedence over global settings.
        If None, fields are inherited from the global configuration.
    """

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
    """Request model for updating video processing status.

    Used by external services (e.g., PMOVES.YT) to report processing results
    back to the channel monitor for tracking and retry logic.

    Attributes:
        video_id: YouTube video ID being updated.
        status: Current processing status (e.g., 'pending', 'processing', 'completed', 'failed').
        error: Optional error message if status is 'failed'.
        metadata: Optional additional metadata about the video or processing result.

    Notes:
        Requires authentication via X-Channel-Monitor-Token header.
    """

    video_id: str
    status: str
    error: str | None = None
    metadata: Dict[str, Any] | None = None


class OAuthTokenRequest(BaseModel):
    """Request model for registering or updating an OAuth token.

    Stores OAuth credentials for user-specific channel monitoring,
    enabling access to private channels, playlists, and liked videos.

    Attributes:
        user_id: Supabase user UUID identifying the token owner.
        provider: OAuth provider key (e.g., 'youtube'). Default is 'youtube'.
        refresh_token: OAuth refresh token for obtaining access tokens.
        scope: List of granted OAuth scopes/permissions.
        expires_at: Optional token expiry timestamp in UTC.
        expires_in: Optional seconds until token expiry (used if expires_at is None).

    Raises:
        ValueError: If scope is not a string, list, or empty value.

    Notes:
        The scope field is normalized to a list of strings regardless of input format.
        Token expiry can be specified either as a timestamp (expires_at) or
        relative duration (expires_in), with expires_at taking precedence.
    """

    user_id: str = Field(..., description="Supabase user UUID")
    provider: str = Field("youtube", description="OAuth provider key")
    refresh_token: str = Field(..., description="OAuth refresh token")
    scope: List[str] = Field(default_factory=list)
    expires_at: datetime | None = Field(None, description="Token expiry timestamp (UTC)")
    expires_in: int | None = Field(None, description="Seconds until token expiry (if expires_at missing)")

    @validator("scope", pre=True)
    def _normalize_scope(cls, value):  # type: ignore[no-untyped-def]
        """Normalize OAuth scope field to a list of strings.

        Args:
            value: Scope value as string, list, or None/empty.

        Returns:
            List of non-empty scope strings.

        Raises:
            ValueError: If value is not a string, list, or empty value.
        """
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [token for token in value.replace(",", " ").split() if token]
        if isinstance(value, list):
            return [token for token in value if isinstance(token, str)]
        raise ValueError("scope must be a string or list of strings")


class UserSourceRequest(BaseModel):
    """Request model for registering a user-specific content source.

    User sources are tied to OAuth tokens and can monitor private content
    such as personal playlists, liked videos, or subscriptions.

    Attributes:
        user_id: Supabase user UUID identifying the source owner.
        provider: Media platform provider (e.g., 'youtube'). Default is 'youtube'.
        source_type: Type of source ('channel', 'playlist', 'likes', 'user').
        source_identifier: Stable identifier (channel ID, playlist ID, etc.).
        source_url: Canonical URL for the source.
        namespace: Namespace for multi-tenant isolation. Uses default if None.
        tags: List of tags for categorization and filtering.
        auto_process: Whether to automatically process new content. Default is True.
        check_interval_minutes: Check interval in minutes. Must be >= 1. Uses default if None.
        filters: Additional filters for content processing.
        yt_options: YouTube-specific options for yt-dlp or youtube-dl.
        token_id: Linked OAuth token ID for authenticated access.
        status: Source status ('active', 'paused', 'error'). Default is 'active'.

    Notes:
        Private sources require a valid token_id linking to an OAuth token
        with appropriate scopes.
    """

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
    """Verify authentication token for protected endpoints.

    FastAPI dependency that validates the X-Channel-Monitor-Token header
    against the configured secret. Bypassed if no secret is configured.

    Args:
        token: Token value from X-Channel-Monitor-Token header. Can be None.

    Returns:
        None if authentication succeeds.

    Raises:
        HTTPException: 401 if token is invalid, missing, or doesn't match STATUS_SECRET.

    Notes:
        If STATUS_SECRET is None or empty, authentication is bypassed.
        Use this dependency to protect sensitive endpoints like status updates.
    """
    if STATUS_SECRET and token != STATUS_SECRET:
        raise HTTPException(status_code=401, detail="invalid or missing token")
    return None


def get_monitor(request: Request) -> ChannelMonitor:
    """Retrieve the ChannelMonitor instance from application state.

    FastAPI dependency that provides access to the singleton ChannelMonitor
    instance stored in app.state during lifespan startup.

    Args:
        request: FastAPI Request object containing app.state.

    Returns:
        ChannelMonitor instance.

    Raises:
        HTTPException: 503 if monitor has not been initialized (service unavailable).

    Notes:
        The monitor is initialized during application startup in the lifespan context manager.
        Use this dependency to inject the monitor into endpoint handlers.
    """
    instance = getattr(request.app.state, "monitor", None)
    if instance is None:
        raise HTTPException(status_code=503, detail="monitor not initialized")
    return instance


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    """Kubernetes-style health check endpoint.

    Provides a lightweight health probe for container orchestration and
    monitoring systems. Returns service status and configuration summary.

    Returns:
        Dictionary containing:
            - 'status': 'ok' if service is healthy
            - 'queue_url': Configured ingestion queue URL
            - 'database_url': Configured database connection string
            - 'channels': Number of channels currently being monitored

    Notes:
        This endpoint does not require authentication and is suitable for
        use as a Kubernetes liveness/readiness probe.
    """
    return {
        "status": "ok",
        "queue_url": QUEUE_URL,
        "database_url": DATABASE_URL,
        "channels": monitor.channel_count(),
    }


@app.get("/api/monitor/stats")
async def stats():
    """Retrieve comprehensive monitoring statistics.

    Returns detailed statistics about the channel monitor service including
    channel counts, check intervals, processing status, and error rates.

    Returns:
        Dictionary with monitoring statistics from ChannelMonitor.get_stats().

    Notes:
        This is an async endpoint that queries the database for current stats.
    """
    return await monitor.get_stats()


@app.get("/api/monitor/channels")
async def channels():
    """List all configured channels.

    Returns a list of all channels currently configured for monitoring,
    including their settings and status.

    Returns:
        List of channel configurations from ChannelMonitor.list_channels().

    Notes:
        Does not include user-specific sources. Use /api/monitor/user-sources
        for user-specific content sources.
    """
    return monitor.list_channels()


@app.post("/api/monitor/check-now")
async def trigger_check(monitor: ChannelMonitor = Depends(get_monitor)):
    """Trigger an immediate check of all enabled channels.

    Forces the monitor to check all channels for new content immediately,
    bypassing the scheduled check interval.

    Args:
        monitor: ChannelMonitor instance injected via dependency.

    Returns:
        Dictionary with 'status': 'ok' on successful trigger.

    Notes:
        Increments the 'channel_monitor_checks_total' Prometheus metric
        with kind='manual' label. This is a fire-and-forget operation;
        the check runs in the background.
    """
    await monitor.check_all_channels()
    CHANNEL_CHECKS_TOTAL.labels(kind="manual").inc()
    return {"status": "ok"}


@app.post("/api/monitor/channel")
async def add_channel(payload: AddChannelRequest, monitor: ChannelMonitor = Depends(get_monitor)):
    """Add a new channel to monitor.

    Registers a new YouTube channel for monitoring with the specified
    configuration. The channel will be checked periodically based on
    the check_interval_minutes setting.

    Args:
        payload: Channel configuration from request body.
        monitor: ChannelMonitor instance injected via dependency.

    Returns:
        Dictionary with:
            - 'status': 'ok' on success
            - 'channel': The created channel configuration

    Raises:
        HTTPException: 400 if channel configuration is invalid (ValueError).

    Notes:
        Updates the in-memory configuration and persists to the config file.
        The channel will be checked on the next scheduled interval or
        can be triggered immediately via /api/monitor/check-now.
    """
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
    """Update video processing status.

    Webhook endpoint called by external services (e.g., PMOVES.YT) to report
    processing results for videos. Updates the video status and optionally
    stores error information or metadata.

    Args:
        payload: Status update containing video_id, status, error, and metadata.
        _: Authentication token verified via require_secret dependency.
        monitor: ChannelMonitor instance injected via dependency.

    Returns:
        Dictionary with:
            - 'status': 'ok' on success
            - 'updated': The updated video record

    Raises:
        HTTPException: 400 if video_id is not found (ValueError).
        HTTPException: 401 if authentication token is invalid.

    Notes:
        Requires authentication via X-Channel-Monitor-Token header.
        Increments 'channel_monitor_status_updates_total' Prometheus metric
        with result='success' label.
    """
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
    """Lightweight status probe for monitoring systems.

    Provides a minimal health check endpoint that does not require authentication.
    Intended for use by blackbox monitoring and alerting systems.

    Returns:
        Dictionary containing:
            - 'status': 'ok' if service is healthy
            - 'service': 'channel-monitor'

    Raises:
        HTTPException: 503 if an unexpected error occurs.

    Notes:
        This endpoint is distinct from /healthz which provides more detailed
        information. Use /api/monitor/stats for comprehensive statistics.
        Does not require authentication for monitoring convenience.
    """
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
    """Prometheus metrics endpoint.

    Exposes Prometheus metrics for monitoring and observability.
    Metrics include channel check counts, status update counts,
    and standard process/runtime metrics.

    Returns:
        PlainTextResponse with Prometheus exposition format metrics.
        Content-Type is set to CONTENT_TYPE_LATEST.

    Notes:
        This endpoint does not require authentication.
        Metrics include:
        - channel_monitor_checks_total: Total channel checks by kind (startup, manual, scheduled)
        - channel_monitor_status_updates_total: Total status updates by result (success, error)
        Standard Python runtime metrics are also included.
    """
    data = generate_latest()  # type: ignore[arg-type]
    return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)


@app.post("/api/oauth/google/token")
async def upsert_google_token(
    payload: OAuthTokenRequest,
    monitor: ChannelMonitor = Depends(get_monitor),
):
    """Register or update a Google OAuth token.

    Stores OAuth refresh token for a user, enabling authenticated access
    to private YouTube content (subscriptions, playlists, liked videos).

    Args:
        payload: OAuth token request with user_id, refresh_token, scopes, etc.
        monitor: ChannelMonitor instance injected via dependency.

    Returns:
        Dictionary with:
            - 'status': 'ok' on success
            - 'token_id': UUID of the created/updated token

    Notes:
        Tokens are encrypted at rest in the database.
        Existing tokens for the same user_id and provider are updated.
        The token_id can be referenced in UserSourceRequest for private sources.
    """
    token_id = await monitor.upsert_user_token(payload.dict())
    return {"status": "ok", "token_id": str(token_id)}


@app.post("/api/monitor/user-source")
async def register_user_source(
    payload: UserSourceRequest,
    monitor: ChannelMonitor = Depends(get_monitor),
):
    """Register or update a user-specific content source.

    Creates a content source tied to a specific user via OAuth token.
    Can monitor private channels, playlists, liked videos, and subscriptions.

    Args:
        payload: User source configuration with source_type, token_id, etc.
        monitor: ChannelMonitor instance injected via dependency.

    Returns:
        Dictionary with:
            - 'status': 'ok' on success
            - 'source': The created/updated source configuration

    Notes:
        Private sources require a valid token_id referencing an OAuth token.
        The token must have appropriate scopes for the source_type.
        For example, 'likes' sources require 'https://www.googleapis.com/auth/youtube.readonly'.
    """
    source = await monitor.upsert_user_source(payload.dict())
    return {"status": "ok", "source": source}


@app.get("/api/monitor/user-sources")
async def list_user_sources(monitor: ChannelMonitor = Depends(get_monitor)):
    """List all user-specific content sources.

    Returns a list of all user sources configured for monitoring,
    including their settings, status, and linked OAuth tokens.

    Args:
        monitor: ChannelMonitor instance injected via dependency.

    Returns:
        Dictionary with:
            - 'status': 'ok'
            - 'sources': List of user source configurations

    Notes:
        Does not include global channels. Use /api/monitor/channels for
        globally monitored channels.
    """
    sources = await monitor.list_user_sources()
    return {"status": "ok", "sources": sources}
