from contextlib import asynccontextmanager

import asyncio
import base64
import contextlib
import datetime
import json
import logging
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import httpx
from fastapi import Body, FastAPI, HTTPException
from nats.aio.client import Client as NATS

try:
    _services_root = Path(__file__).resolve().parents[2]
    if str(_services_root) not in sys.path:
        sys.path.insert(0, str(_services_root))
except Exception:
    pass

try:  # pragma: no cover - optional Supabase helper
    from services.common import supabase as supabase_common
except Exception:  # pragma: no cover - supabase is optional for local/dev
    supabase_common = None  # type: ignore[assignment]

from services.common.telemetry import PublisherMetrics, PublishTelemetry, compute_publish_telemetry



# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle Management
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan for Publisher Discord."""
    global _nats_loop_task, _nc
    # Startup - Discord webhooks are configured at runtime
    # Non-blocking, quiet NATS init
    if YT_NATS_ENABLE and NATS_URL:
        logger.info(
            "nats_loop_start",
            extra={"event": "nats_loop_start", "servers": [NATS_URL]},
        )
        _nats_loop_task = asyncio.create_task(_nats_resilience_loop())
    yield

    # Shutdown
    if _nats_loop_task:
        _nats_loop_task.cancel()
        with contextlib.suppress(Exception):
            await _nats_loop_task
        _nats_loop_task = None
    if _nc:
        with contextlib.suppress(Exception):
            await _nc.close()
        _nc = None


app = FastAPI(title="Publisher-Discord", version="0.1.0", lifespan=lifespan)

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
# Prefer the n8n-style username if provided, fallback to legacy var
DISCORD_USERNAME = os.environ.get("DISCORD_USERNAME", os.environ.get("DISCORD_WEBHOOK_USERNAME", "PMOVES"))
DISCORD_AVATAR_URL = os.environ.get("DISCORD_AVATAR_URL", "")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
YT_NATS_ENABLE = os.environ.get("YT_NATS_ENABLE", "true").lower() in {"1", "true", "yes", "on"}
SUBJECTS = os.environ.get(
    "DISCORD_SUBJECTS",
    "ingest.file.added.v1,ingest.transcript.ready.v1,ingest.summary.ready.v1,ingest.chapters.ready.v1,content.published.v1,"
    "tokenism.attribution.recorded.v1,tokenism.cgp.weekly.v1,tokenism.cgp.ready.v1,tokenism.swarm.population.v1",
).split(",")

JELLYFIN_URL = os.environ.get("JELLYFIN_URL", "")
# Default to the legacy style expected by tests; allow override.
DISCORD_PUBLISH_PREFIX = os.environ.get("DISCORD_PUBLISH_PREFIX", "Published: ")

DISCORD_METRICS_TABLE = os.environ.get("DISCORD_METRICS_TABLE", "publisher_discord_metrics")
DISCORD_METRICS_CONFLICT = os.environ.get("DISCORD_METRICS_CONFLICT", "published_event_id")

# Claude session thread configuration
CLAUDE_SESSION_CHANNEL_ID = os.environ.get("CLAUDE_SESSION_CHANNEL_ID", "")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")

_nc: Optional[NATS] = None
_nats_loop_task: Optional[asyncio.Task] = None
_webhook_counters = Counter()
_telemetry_metrics = PublisherMetrics()
logger = logging.getLogger("publisher_discord")

# Track session_id -> thread_id mapping for Claude sessions
_session_threads: Dict[str, str] = {}


def _extract_webhook_domain(webhook_url: str) -> str:
    """Extract domain from Discord webhook URL for logging (sanitizes credentials)."""
    # Discord webhook URLs are: https://discord.com/api/webhooks/<id>/<token>
    # Extract just the domain for logging
    try:
        if "discord.com" in webhook_url:
            return "discord.com"
        elif "discord.gg" in webhook_url:
            return "discord.gg"
        else:
            return "unknown"
    except Exception:
        return "invalid"


def _coerce_tags(raw: Any) -> Iterable[str]:
    if isinstance(raw, str):
        candidates = [part.strip() for part in raw.split(",")]
    elif isinstance(raw, Iterable):
        candidates = []
        for item in raw:
            if item is None:
                continue
            if isinstance(item, (str, int, float)):
                value = str(item).strip()
                if value:
                    candidates.append(value)
    else:
        return []
    return [item for item in candidates if item]


def _pick_thumbnail(payload: Dict[str, Any]) -> Optional[str]:
    thumb = payload.get("thumb")
    if isinstance(thumb, str) and thumb:
        return thumb
    cover_art = payload.get("cover_art")
    if isinstance(cover_art, dict):
        direct = cover_art.get("url")
        if isinstance(direct, str) and direct:
            return direct
        thumbs = cover_art.get("thumbnails")
        if isinstance(thumbs, Iterable):
            ranked = []
            for item in thumbs:
                if not isinstance(item, dict):
                    continue
                url = item.get("url")
                if not isinstance(url, str) or not url:
                    continue
                size = 0
                for dim in ("width", "height"):
                    try:
                        size += int(item.get(dim) or 0)
                    except (TypeError, ValueError):
                        continue
                ranked.append((size, url))
            if ranked:
                ranked.sort(reverse=True)
                return ranked[0][1]
    return None


def _coerce_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return str(value)


def _safe_slug(*values: Optional[str]) -> str:
    for value in values:
        if not value:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
        if slug:
            return slug
    return "discord-event"


def _webhook_snapshot() -> Dict[str, int]:
    return {
        "webhook_success": _webhook_counters.get("discord_webhook_success", 0),
        "webhook_failures": _webhook_counters.get("discord_webhook_failures", 0),
        "webhook_missing": _webhook_counters.get("discord_webhook_missing", 0),
    }


def _record_publish_telemetry(telemetry: PublishTelemetry) -> None:
    _telemetry_metrics.record_turnaround(telemetry.turnaround_seconds)
    _telemetry_metrics.record_approval_latency(telemetry.approval_latency_seconds)
    _telemetry_metrics.record_engagement(telemetry.engagement)
    _telemetry_metrics.record_cost(telemetry.cost)


async def _persist_discord_rollup(
    telemetry: PublishTelemetry,
    payload: Dict[str, Any],
    envelope: Dict[str, Any],
    webhook_success: bool,
) -> None:
    if supabase_common is None:
        logger.debug("Supabase client unavailable; skipping Discord metrics rollup persistence")
        return

    artifact_uri = _coerce_text(payload.get("artifact_uri")) or _coerce_text(payload.get("content_url"))
    published_event_id = _coerce_text(envelope.get("id"))
    if not artifact_uri:
        artifact_uri = f"discord::{published_event_id or _safe_slug(payload.get('title'), payload.get('slug'))}"

    namespace = _coerce_text(payload.get("namespace") or payload.get("workspace") or "pmoves") or "pmoves"
    slug = _safe_slug(
        payload.get("slug"),
        payload.get("title"),
        payload.get("published_path"),
        published_event_id,
    )

    row = telemetry.to_rollup_row(
        artifact_uri=artifact_uri,
        namespace=namespace,
        slug=slug,
    )
    row.update(
        {
            "published_event_id": published_event_id,
            "event_topic": _coerce_text(envelope.get("topic") or envelope.get("subject")),
            "channel": "discord",
            "webhook_success": webhook_success,
        }
    )

    try:
        await asyncio.to_thread(
            supabase_common.upsert_row,
            DISCORD_METRICS_TABLE,
            row,
            DISCORD_METRICS_CONFLICT or None,
        )
    except Exception as exc:  # pragma: no cover - external dependency
        logger.warning(
            "Failed to persist Discord metrics rollup",
            extra={"table": DISCORD_METRICS_TABLE, "row": row},
            exc_info=exc,
        )


async def _handle_nats_message(msg):
    try:
        data = json.loads(msg.data.decode("utf-8"))
        envelope: Dict[str, Any] = data if isinstance(data, dict) else {}
    except Exception:
        envelope = {}

    name = envelope.get("topic") or msg.subject
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else envelope or {}
    if not isinstance(payload, dict):
        payload = {"raw": msg.data.decode("utf-8", errors="ignore")}

    # Handle Claude session events differently (use Discord Bot API with threads)
    if name.startswith("claude.code.session."):
        if name == "claude.code.session.start.v1":
            await _handle_claude_session_start(payload)
        elif name == "claude.code.session.context.v1":
            await _handle_claude_session_context(payload)
        elif name == "claude.code.session.end.v1":
            await _handle_claude_session_end(payload)
        logger.info(
            "claude_session_event_processed",
            extra={
                "subject": name,
                "session_id": payload.get("session_id"),
            },
        )
        return

    # Handle regular events (use webhook)
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else None
    published_at = datetime.datetime.now(datetime.timezone.utc)
    telemetry = compute_publish_telemetry(
        meta,
        envelope.get("ts") if isinstance(envelope, dict) else None,
        published_at,
    )
    _record_publish_telemetry(telemetry)

    rendered = _format_event(name, payload)
    ok = await _post_discord(rendered.get("content"), rendered.get("embeds"))
    if not ok:
        logger.warning(
            "discord_delivery_failed",
            extra={
                "event": "discord_delivery_failed",
                "subject": name,
                "nats_subject": msg.subject,
            },
        )

    await _persist_discord_rollup(telemetry, payload, envelope if isinstance(envelope, dict) else {}, ok)
    logger.info(
        "discord_event_processed",
        extra={
            "subject": name,
            "nats_subject": msg.subject,
            "webhook_success": ok,
            "metrics": {
                "webhook": _webhook_snapshot(),
                "telemetry": _telemetry_metrics.summary(),
            },
        },
    )


async def _register_nats_subscriptions(nc: Optional[NATS]) -> None:
    subjects = [subj.strip() for subj in SUBJECTS if subj.strip()]
    if nc is None:
        logger.warning(
            "nats_subscription_skipped",
            extra={
                "event": "nats_subscription_skipped",
                "subjects": subjects,
                "reason": "nats_client_none",
            },
        )
        return

    for subj in subjects:
        try:
            await nc.subscribe(subj, cb=_handle_nats_message)
            logger.info(
                "nats_subscription_registered",
                extra={"event": "nats_subscription_registered", "subject": subj},
            )
        except Exception as exc:
            logger.warning(
                "nats_subscription_failed",
                extra={
                    "event": "nats_subscription_failed",
                    "subject": subj,
                    "error": str(exc),
                },
            )


async def _nats_resilience_loop() -> None:
    backoff = 1.0
    while True:
        nc = NATS()
        disconnect_event = asyncio.Event()

        def _mark_connection_lost(reason: str) -> None:
            global _nc
            if _nc is nc:
                _nc = None
            if not disconnect_event.is_set():
                disconnect_event.set()
            logger.warning(
                "nats_connection_lost",
                extra={
                    "event": "nats_connection_lost",
                    "reason": reason,
                    "servers": [NATS_URL],
                },
            )

        async def _disconnected_cb():
            _mark_connection_lost("disconnected")

        async def _closed_cb():
            _mark_connection_lost("closed")

        try:
            logger.info(
                "nats_connect_attempt",
                extra={"event": "nats_connect_attempt", "servers": [NATS_URL], "backoff": backoff},
            )
            await nc.connect(servers=[NATS_URL], disconnected_cb=_disconnected_cb, closed_cb=_closed_cb)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "nats_connect_failed",
                extra={
                    "event": "nats_connect_failed",
                    "servers": [NATS_URL],
                    "error": str(exc),
                    "backoff": backoff,
                },
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)
            continue

        global _nc
        _nc = nc
        backoff = 1.0
        logger.info(
            "nats_connected",
            extra={"event": "nats_connected", "servers": [NATS_URL]},
        )
        await _register_nats_subscriptions(nc)

        try:
            await disconnect_event.wait()
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await nc.close()
            if _nc is nc:
                _nc = None
            raise

        with contextlib.suppress(Exception):
            await nc.close()


@app.get("/healthz")
async def healthz():
    """Health check endpoint for Kubernetes probes."""
    return {
        "ok": True,
        "webhook": bool(DISCORD_WEBHOOK_URL),
        "metrics": _webhook_snapshot(),
        "telemetry": _telemetry_metrics.summary(),
    }


@app.get("/metrics")
async def metrics():
    """Metrics endpoint for webhook and telemetry statistics."""
    return {
        "webhook": _webhook_snapshot(),
        "telemetry": _telemetry_metrics.summary(),
    }

async def _create_discord_thread(channel_id: str, thread_name: str, message_content: Optional[str] = None, embeds: Optional[list] = None) -> Optional[str]:
    """Create a new Discord thread in the specified channel. Returns thread_id or None on failure."""
    if not DISCORD_BOT_TOKEN or not channel_id:
        logger.warning("discord_thread_create_skipped", extra={"event": "discord_thread_create_skipped", "reason": "missing_bot_token_or_channel"})
        return None

    # First, post a message to the channel
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {}
    if message_content:
        payload["content"] = message_content
    if embeds:
        payload["embeds"] = embeds

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            # Create a message in the channel
            r = await client.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers=headers,
                json=payload
            )
            if r.status_code not in (200, 201):
                logger.warning(
                    "discord_message_create_failed",
                    extra={"event": "discord_message_create_failed", "status": r.status_code, "body": r.text[:256]}
                )
                return None

            message_data = r.json()
            message_id = message_data.get("id")

            if not message_id:
                logger.warning("discord_message_no_id", extra={"event": "discord_message_no_id"})
                return None

            # Create a thread from the message
            thread_payload = {"name": thread_name[:100], "auto_archive_duration": 1440}  # 24 hours
            r = await client.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/threads",
                headers=headers,
                json=thread_payload
            )

            if r.status_code not in (200, 201):
                logger.warning(
                    "discord_thread_create_failed",
                    extra={"event": "discord_thread_create_failed", "status": r.status_code, "body": r.text[:256]}
                )
                return None

            thread_data = r.json()
            thread_id = thread_data.get("id")

            if thread_id:
                logger.info("discord_thread_created", extra={"event": "discord_thread_created", "thread_id": thread_id, "name": thread_name})

            return thread_id

        except Exception as exc:
            logger.warning("discord_thread_create_exception", extra={"event": "discord_thread_create_exception", "error": str(exc)})
            return None


async def _post_to_discord_thread(thread_id: str, content: Optional[str] = None, embeds: Optional[list] = None) -> bool:
    """Post a message to an existing Discord thread."""
    if not DISCORD_BOT_TOKEN or not thread_id:
        logger.warning("discord_thread_post_skipped", extra={"event": "discord_thread_post_skipped", "reason": "missing_bot_token_or_thread_id"})
        return False

    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.post(
                f"https://discord.com/api/v10/channels/{thread_id}/messages",
                headers=headers,
                json=payload
            )

            if r.status_code in (200, 201):
                return True

            logger.warning(
                "discord_thread_post_failed",
                extra={"event": "discord_thread_post_failed", "status": r.status_code, "body": r.text[:256]}
            )
            return False

        except Exception as exc:
            logger.warning("discord_thread_post_exception", extra={"event": "discord_thread_post_exception", "error": str(exc)})
            return False


async def _post_discord(content: Optional[str], embeds: Optional[list] = None, retries: int = 3):
    if not DISCORD_WEBHOOK_URL:
        logger.warning("discord_webhook_missing", extra={"event": "discord_webhook_missing"})
        _webhook_counters["discord_webhook_missing"] += 1
        return False
    payload = {"username": DISCORD_USERNAME}
    if DISCORD_AVATAR_URL:
        payload["avatar_url"] = DISCORD_AVATAR_URL
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds
    backoff = 1.0
    async with httpx.AsyncClient(timeout=15) as client:
        for attempt in range(max(1, retries)):
            try:
                r = await client.post(DISCORD_WEBHOOK_URL, json=payload)
            except Exception as exc:
                logger.warning(
                    "discord_webhook_exception",
                    extra={
                        "event": "discord_webhook_exception",
                        "error": str(exc),
                        "attempt": attempt + 1,
                    },
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 8.0)
                continue
            if r.status_code in (200, 204):
                _webhook_counters["discord_webhook_success"] += 1
                return True
            if r.status_code == 429:
                try:
                    ra = float(r.headers.get("Retry-After", backoff))
                except Exception:
                    ra = backoff
                await asyncio.sleep(ra)
                backoff = min(backoff * 2.0, 8.0)
                continue
            if 500 <= r.status_code < 600:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 8.0)
                continue
            logger.warning(
                "discord_webhook_failed",
                extra={
                    "event": "discord_webhook_failed",
                    "status_code": r.status_code,
                    "attempt": attempt + 1,
                    "body": r.text[:256],
                },
            )
            _webhook_counters["discord_webhook_failures"] += 1
            return False
    logger.warning(
        "discord_webhook_failed",
        extra={"event": "discord_webhook_failed", "status_code": None, "attempt": retries},
    )
    _webhook_counters["discord_webhook_failures"] += 1
    return False


def _decode_publish_file(obj: Any) -> Optional[dict]:
    """
    Accept a small file payload for webhook attachment.

    Shape:
      {
        "name": "voice.wav",
        "content_type": "audio/wav",
        "content_b64": "..."
      }
    """
    if not isinstance(obj, dict):
        return None
    name = obj.get("name") or obj.get("filename")
    content_b64 = obj.get("content_b64") or obj.get("b64")
    content_type = obj.get("content_type") or obj.get("type") or "application/octet-stream"
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(content_b64, str) or not content_b64.strip():
        return None
    try:
        # Be strict: reject malformed base64 rather than silently producing tiny/garbled files.
        cleaned = re.sub(r"\s+", "", content_b64.strip())
        raw = base64.b64decode(cleaned.encode("ascii"), validate=True)
    except Exception:
        return None
    # Discord webhooks: 8MB typical limit; keep tighter to avoid noisy failures.
    if len(raw) == 0 or len(raw) > 7_500_000:
        return None
    # Guard against "success" uploads that are effectively empty (e.g. bad base64 decoded as a few bytes).
    if str(content_type).lower().startswith("audio/") and len(raw) < 1024:
        return None
    return {"name": name.strip(), "content_type": str(content_type), "bytes": raw}


async def _post_discord_with_file(
    content: Optional[str],
    embeds: Optional[list],
    file_name: str,
    file_bytes: bytes,
    file_content_type: str,
    retries: int = 3,
) -> bool:
    if not DISCORD_WEBHOOK_URL:
        logger.warning("discord_webhook_missing", extra={"event": "discord_webhook_missing"})
        _webhook_counters["discord_webhook_missing"] += 1
        return False

    payload = {"username": DISCORD_USERNAME}
    if DISCORD_AVATAR_URL:
        payload["avatar_url"] = DISCORD_AVATAR_URL
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    # Discord expects multipart with payload_json + files[0]
    data = {"payload_json": json.dumps(payload)}
    files = {"files[0]": (file_name, file_bytes, file_content_type)}

    backoff = 1.0
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(max(1, retries)):
            try:
                r = await client.post(DISCORD_WEBHOOK_URL, data=data, files=files)
            except Exception as exc:
                logger.warning(
                    "discord_webhook_exception",
                    extra={
                        "event": "discord_webhook_exception",
                        "error": str(exc),
                        "attempt": attempt + 1,
                    },
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 8.0)
                continue
            if r.status_code in (200, 204):
                _webhook_counters["discord_webhook_success"] += 1
                return True
            if r.status_code == 429:
                try:
                    ra = float(r.headers.get("Retry-After", backoff))
                except Exception:
                    ra = backoff
                await asyncio.sleep(ra)
                backoff = min(backoff * 2.0, 8.0)
                continue
            if 500 <= r.status_code < 600:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 8.0)
                continue
            logger.warning(
                "discord_webhook_failed",
                extra={
                    "event": "discord_webhook_failed",
                    "status_code": r.status_code,
                    "attempt": attempt + 1,
                    "body": r.text[:256],
                },
            )
            _webhook_counters["discord_webhook_failures"] += 1
            return False

    logger.warning(
        "discord_webhook_failed",
        extra={"event": "discord_webhook_failed", "status_code": None, "attempt": retries},
    )
    _webhook_counters["discord_webhook_failures"] += 1
    return False


def _safe_format_number(
    value: Any,
    fmt: str = ".2f",
    prefix: str = "",
    suffix: str = "",
    fallback: str = "N/A",
) -> str:
    """Safely format a numeric value with defensive error handling.

    Args:
        value: The value to format (should be numeric).
        fmt: Format specifier (e.g., ".2f", ",.0f", ".4f").
        prefix: String to prepend (e.g., "$").
        suffix: String to append (e.g., "%").
        fallback: Value to return if formatting fails.

    Returns:
        Formatted string or fallback if value is not numeric.
    """
    if value is None:
        return fallback
    try:
        formatted = f"{float(value):{fmt}}"
        return f"{prefix}{formatted}{suffix}"
    except (TypeError, ValueError):
        return fallback


def _format_event(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    name = name.strip()
    emb = {"title": name, "fields": []}
    color_map = {
        "ingest.file.added.v1": 0x2b90d9,
        "ingest.transcript.ready.v1": 0x10b981,
        "ingest.summary.ready.v1": 0xf59e0b,
        "ingest.chapters.ready.v1": 0x8b5cf6,
        "content.published.v1": 0x22c55e,
        # CHIT / ToKenism colors (teal/cyan spectrum)
        "tokenism.attribution.recorded.v1": 0x00d4aa,
        "tokenism.cgp.weekly.v1": 0x06b6d4,
        "tokenism.cgp.ready.v1": 0x0891b2,
        "tokenism.swarm.population.v1": 0x14b8a6,
    }
    emb["color"] = color_map.get(name, 0x94a3b8)  # default slate-400
    thumb = _pick_thumbnail(payload)
    if name == "ingest.file.added.v1":
        title = payload.get("title") or payload.get("key")
        emb["title"] = f"Ingest: {title}"
        emb["fields"].append({"name":"Bucket", "value": str(payload.get("bucket")), "inline": True})
        emb["fields"].append({"name":"Namespace", "value": str(payload.get("namespace")), "inline": True})
        if payload.get("video_id"):
            emb["fields"].append({"name":"Video ID", "value": str(payload.get("video_id")), "inline": True})
        # Optional link to the asset if provided
        if isinstance(payload.get("content_url"), str):
            emb["url"] = payload.get("content_url")
    elif name == "ingest.transcript.ready.v1":
        emb["title"] = f"Transcript ready: {payload.get('video_id')}"
        emb["fields"].append({"name":"Language", "value": str(payload.get("language") or "auto"), "inline": True})
        if payload.get("s3_uri"):
            emb["fields"].append({"name":"Audio", "value": payload.get("s3_uri"), "inline": False})
    elif name == "ingest.summary.ready.v1":
        summ = payload.get("summary") or ""
        emb["title"] = f"Summary: {payload.get('video_id')}"
        emb["description"] = (summ[:1800] + ("…" if len(summ) > 1800 else ""))
    elif name == "ingest.chapters.ready.v1":
        ch = payload.get("chapters") or []
        emb["title"] = f"Chapters: {payload.get('video_id')} ({len(ch)} items)"
        if ch:
            sample = "\n".join(f"• {c.get('title')}" for c in ch[:6])
            emb["description"] = sample
    elif name == "content.published.v1":
        title = payload.get("title") or payload.get("slug") or payload.get("published_path")
        if DISCORD_PUBLISH_PREFIX:
            emb["title"] = f"{DISCORD_PUBLISH_PREFIX}{title or 'content'}"
        else:
            emb["title"] = f"{title or 'content'}"
        public_url = payload.get("public_url") or payload.get("jellyfin_public_url")
        published_path = payload.get("published_path")
        namespace = payload.get("namespace") or payload.get("workspace")
        artifact_uri = payload.get("artifact_uri")
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        jellyfin_item_id = payload.get("jellyfin_item_id") or meta.get("jellyfin_item_id")
        jellyfin_public_url = (
            payload.get("jellyfin_public_url")
            or (meta.get("jellyfin_public_url") if isinstance(meta, dict) else None)
        )
        duration_s = None
        for k in ("duration",):
            try:
                v = payload.get(k)
                if v is None and meta:
                    v = meta.get(k)
                if v is not None:
                    duration_s = float(v)
            except (TypeError, ValueError):
                pass
        def _fmt_dur(sec: float) -> str:
            try:
                total = int(round(float(sec)))
                hours, remainder = divmod(total, 3600)
                minutes, seconds = divmod(remainder, 60)
                return f"{hours:d}:{minutes:02d}:{seconds:02d}"
            except Exception:
                return str(sec)
        description_lines = []
        if isinstance(public_url, str) and public_url:
            emb["url"] = public_url
            description_lines.append(f"[Open published content]({public_url})")
            emb["fields"].append({"name": "Public URL", "value": public_url, "inline": False})
        else:
            emb["fields"].append({"name": "Public URL", "value": "_not available_", "inline": False})
            if published_path:
                description_lines.append(f"Path: `{published_path}`")
        if namespace:
            emb["fields"].append({"name": "Namespace", "value": str(namespace), "inline": True})
            if not public_url:
                description_lines.append(f"Namespace: `{namespace}`")
        if published_path:
            emb["fields"].append({"name": "Published Path", "value": f"`{published_path}`", "inline": False})
        if artifact_uri:
            emb["fields"].append({"name": "Artifact URI", "value": str(artifact_uri), "inline": False})
        if duration_s is not None:
            emb["fields"].append({"name": "Duration", "value": _fmt_dur(duration_s), "inline": True})
        if jellyfin_item_id:
            emb["fields"].append({"name": "Jellyfin Item", "value": f"`{jellyfin_item_id}`", "inline": True})
            if jellyfin_public_url:
                emb["fields"].append({"name": "Jellyfin", "value": jellyfin_public_url, "inline": False})
            else:
                # Build deep link when a base URL is available (payload/meta or env JELLYFIN_URL)
                jf_base = (
                    payload.get("jellyfin_base_url")
                    or (meta.get("jellyfin_base_url") if isinstance(meta, dict) else None)
                    or JELLYFIN_URL
                )
                if isinstance(jf_base, str) and jf_base:
                    jf_base = jf_base.rstrip("/")
                    timestamp_candidates = [
                        payload.get("t"),
                        payload.get("start"),
                        payload.get("start_time"),
                        payload.get("position"),
                    ]
                    if isinstance(meta, dict):
                        timestamp_candidates.extend(
                            meta.get(key)
                            for key in ("t", "start", "start_time", "timestamp", "position")
                        )
                    tparam = ""
                    for candidate in timestamp_candidates:
                        if candidate is None or candidate == "":
                            continue
                        try:
                            seconds = int(round(float(candidate)))
                            if seconds < 0:
                                continue
                            tparam = f"&startTime={seconds}"
                            break
                        except (TypeError, ValueError):
                            continue
                    jf_link = f"{jf_base}/web/index.html#!/details?id={jellyfin_item_id}{tparam}"
                    emb["fields"].append({"name": "Jellyfin", "value": jf_link, "inline": False})
        tags_source = payload.get("tags")
        if not tags_source and isinstance(meta, dict):
            tags_source = meta.get("tags")
        tags = list(_coerce_tags(tags_source))
        if tags:
            formatted_tags = ", ".join(f"`{tag}`" for tag in tags[:12])
            emb["fields"].append({"name": "Tags", "value": formatted_tags, "inline": False})
        if description_lines:
            emb["description"] = "\n".join(description_lines)
        summary_source = payload.get("summary") or payload.get("description")
        if not summary_source and isinstance(meta, dict):
            summary_source = meta.get("summary")
        if summary_source:
            summary_text = str(summary_source)
            if "description" not in emb:
                emb["description"] = summary_text[:1800]
                overflow = summary_text[1800:]
                if overflow:
                    emb["fields"].append(
                        {"name": "Summary (cont.)", "value": overflow[:1024], "inline": False}
                    )
            else:
                emb["fields"].append({"name": "Summary", "value": summary_text[:1024], "inline": False})
    # CHIT / ToKenism event handlers
    elif name == "tokenism.attribution.recorded.v1":
        chit_id = payload.get("chit_id") or payload.get("chitId")
        emb["title"] = f"Attribution Recorded: {chit_id}"
        if payload.get("address"):
            emb["fields"].append({"name": "Address", "value": f"`{payload['address']}`", "inline": True})
        if payload.get("action"):
            emb["fields"].append({"name": "Action", "value": str(payload["action"]), "inline": True})
        if payload.get("amount") is not None:
            emb["fields"].append({"name": "Amount", "value": _safe_format_number(payload["amount"], ",.2f", "$"), "inline": True})
        if payload.get("week") is not None:
            emb["fields"].append({"name": "Week", "value": str(payload["week"]), "inline": True})
        if payload.get("merkle_root"):
            emb["fields"].append({"name": "Merkle Root", "value": f"`{payload['merkle_root'][:16]}...`", "inline": False})
    elif name == "tokenism.cgp.weekly.v1":
        week = payload.get("week")
        emb["title"] = f"ToKenism Week {week} CGP Ready"
        emb["description"] = f"New CGP packet with {payload.get('super_node_count', 0)} super nodes generated."
        if payload.get("gini") is not None:
            emb["fields"].append({"name": "Gini", "value": _safe_format_number(payload["gini"], ".4f"), "inline": True})
        if payload.get("poverty_rate") is not None:
            # Multiply by 100 for percentage display, with defensive handling
            try:
                pct_value = float(payload["poverty_rate"]) * 100
                emb["fields"].append({"name": "Poverty Rate", "value": f"{pct_value:.1f}%", "inline": True})
            except (TypeError, ValueError):
                emb["fields"].append({"name": "Poverty Rate", "value": "N/A", "inline": True})
        if payload.get("total_wealth") is not None:
            emb["fields"].append({"name": "Total Wealth", "value": _safe_format_number(payload["total_wealth"], ",.0f", "$"), "inline": True})
        if payload.get("total_attributions") is not None:
            emb["fields"].append({"name": "Attributions", "value": str(payload["total_attributions"]), "inline": True})
        if payload.get("cgp_spec"):
            emb["fields"].append({"name": "Spec", "value": f"`{payload['cgp_spec']}`", "inline": True})
    elif name == "tokenism.cgp.ready.v1":
        emb["title"] = "CGP Packet Ready"
        emb["description"] = "CHIT Geometry Packet available for consumption."
        if payload.get("week"):
            emb["fields"].append({"name": "Week", "value": str(payload["week"]), "inline": True})
        if payload.get("super_node_count"):
            emb["fields"].append({"name": "Super Nodes", "value": str(payload["super_node_count"]), "inline": True})
    elif name == "tokenism.swarm.population.v1":
        pop_name = payload.get("name") or payload.get("population_id")
        emb["title"] = f"Swarm Population: {pop_name}"
        emb["description"] = "ToKenism swarm optimization update."
        if payload.get("generations"):
            emb["fields"].append({"name": "Generations", "value": str(payload["generations"]), "inline": True})
        if payload.get("best_fitness") is not None:
            emb["fields"].append({"name": "Best Fitness", "value": _safe_format_number(payload["best_fitness"], ".4f"), "inline": True})
        if payload.get("avg_fitness") is not None:
            emb["fields"].append({"name": "Avg Fitness", "value": _safe_format_number(payload["avg_fitness"], ".4f"), "inline": True})
        if payload.get("fitness_improvement") is not None:
            # Format improvement with sign prefix, defensive handling
            try:
                imp = float(payload["fitness_improvement"])
                sign = "+" if imp > 0 else ""
                emb["fields"].append({"name": "Improvement", "value": f"{sign}{imp:.4f}", "inline": True})
            except (TypeError, ValueError):
                emb["fields"].append({"name": "Improvement", "value": "N/A", "inline": True})
        if payload.get("optimization_target"):
            emb["fields"].append({"name": "Target", "value": str(payload["optimization_target"]), "inline": True})
    else:
        desc = json.dumps(payload)[:1800]
        emb["description"] = f"```json\n{desc}\n```"
    # Prefer explicit thumbnail_url in payload/meta, then fall back to auto-pick
    explicit_thumb = None
    if isinstance(payload.get("thumbnail_url"), str) and payload.get("thumbnail_url"):
        explicit_thumb = payload.get("thumbnail_url")
    elif isinstance(payload.get("meta"), dict) and isinstance(payload["meta"].get("thumbnail_url"), str) and payload["meta"]["thumbnail_url"]:
        explicit_thumb = payload["meta"]["thumbnail_url"]

    if explicit_thumb:
        emb["thumbnail"] = {"url": explicit_thumb}
    elif thumb:
        emb["thumbnail"] = {"url": thumb}
    return {"content": None, "embeds": [emb]}


async def _handle_claude_session_start(payload: Dict[str, Any]) -> None:
    """Handle claude.code.session.start.v1 event by creating a Discord thread."""
    session_id = payload.get("session_id")
    if not session_id or not CLAUDE_SESSION_CHANNEL_ID:
        logger.debug("claude_session_start_skipped", extra={"session_id": session_id, "has_channel": bool(CLAUDE_SESSION_CHANNEL_ID)})
        return

    # Build thread name
    branch = payload.get("branch") or "unknown"
    initial_prompt = payload.get("initial_prompt") or ""
    summary_preview = initial_prompt[:50] if initial_prompt else "New session"
    thread_name = f"Claude: {branch} - {summary_preview}"

    # Build embed for the initial message
    emb = {
        "title": f"Claude Session Started",
        "color": 0x5865f2,  # Discord blurple
        "fields": []
    }

    if payload.get("branch"):
        emb["fields"].append({"name": "Branch", "value": f"`{payload['branch']}`", "inline": True})
    if payload.get("worktree"):
        emb["fields"].append({"name": "Worktree", "value": f"`{payload['worktree']}`", "inline": True})
    if payload.get("repository"):
        emb["fields"].append({"name": "Repository", "value": payload["repository"], "inline": True})
    if payload.get("model"):
        emb["fields"].append({"name": "Model", "value": payload["model"], "inline": True})
    if payload.get("parent_session_id"):
        emb["fields"].append({"name": "Resumed from", "value": f"`{payload['parent_session_id']}`", "inline": False})

    if initial_prompt:
        emb["description"] = initial_prompt[:1000]

    emb["footer"] = {"text": f"Session ID: {session_id}"}
    emb["timestamp"] = payload.get("timestamp")

    # Create thread
    thread_id = await _create_discord_thread(CLAUDE_SESSION_CHANNEL_ID, thread_name, embeds=[emb])

    if thread_id:
        _session_threads[session_id] = thread_id
        logger.info("claude_session_thread_created", extra={"session_id": session_id, "thread_id": thread_id})


async def _handle_claude_session_context(payload: Dict[str, Any]) -> None:
    """Handle claude.code.session.context.v1 event by posting updates to the thread."""
    session_id = payload.get("session_id")
    if not session_id:
        return

    thread_id = _session_threads.get(session_id)
    if not thread_id:
        logger.debug("claude_context_no_thread", extra={"session_id": session_id})
        return

    context_type = payload.get("context_type", "update")

    # Build embed
    emb = {
        "title": f"Context Update: {context_type}",
        "color": 0xfee75c,  # Discord yellow
        "fields": []
    }

    if payload.get("summary"):
        emb["description"] = payload["summary"][:2000]

    if payload.get("branch"):
        emb["fields"].append({"name": "Branch", "value": f"`{payload['branch']}`", "inline": True})

    # Show pending tasks
    pending_tasks = payload.get("pending_tasks", [])
    if pending_tasks:
        pending_count = sum(1 for t in pending_tasks if t.get("status") in ("pending", "in_progress"))
        completed_count = sum(1 for t in pending_tasks if t.get("status") == "completed")
        emb["fields"].append({"name": "Tasks", "value": f"{completed_count} completed, {pending_count} pending", "inline": True})

        # Show first few pending tasks
        pending_list = [t for t in pending_tasks if t.get("status") in ("pending", "in_progress")][:3]
        if pending_list:
            task_text = "\n".join(f"• {t.get('content', 'Unknown task')[:80]}" for t in pending_list)
            emb["fields"].append({"name": "Current Tasks", "value": task_text, "inline": False})

    # Show active files
    active_files = payload.get("active_files", [])
    if active_files:
        files_text = "\n".join(f"• `{f.get('path', 'unknown')}` ({f.get('action', 'modified')})" for f in active_files[:5])
        emb["fields"].append({"name": "Active Files", "value": files_text, "inline": False})

    # Show CGP geometry summary if present
    cgp = payload.get("cgp_geometry")
    if cgp and isinstance(cgp, dict):
        emb["fields"].append({"name": "CGP Geometry", "value": f"Type: {cgp.get('type', 'unknown')}", "inline": True})

    emb["timestamp"] = payload.get("timestamp")

    await _post_to_discord_thread(thread_id, embeds=[emb])


async def _handle_claude_session_end(payload: Dict[str, Any]) -> None:
    """Handle claude.code.session.end.v1 event by posting final summary."""
    session_id = payload.get("session_id")
    if not session_id:
        return

    thread_id = _session_threads.get(session_id)
    if not thread_id:
        logger.debug("claude_end_no_thread", extra={"session_id": session_id})
        return

    end_reason = payload.get("end_reason", "unknown")

    # Build embed
    emb = {
        "title": f"Session Ended: {end_reason}",
        "color": 0xeb459e,  # Discord pink
        "fields": []
    }

    if payload.get("summary"):
        emb["description"] = payload["summary"][:2000]

    if payload.get("duration_seconds"):
        duration = payload["duration_seconds"]
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
        emb["fields"].append({"name": "Duration", "value": duration_str, "inline": True})

    tasks_completed = payload.get("tasks_completed", 0)
    tasks_pending = payload.get("tasks_pending", 0)
    if tasks_completed or tasks_pending:
        emb["fields"].append({"name": "Tasks", "value": f"{tasks_completed} completed, {tasks_pending} pending", "inline": True})

    files_modified = payload.get("files_modified", [])
    if files_modified:
        files_text = "\n".join(f"• `{f}`" for f in files_modified[:10])
        if len(files_modified) > 10:
            files_text += f"\n... and {len(files_modified) - 10} more"
        emb["fields"].append({"name": "Files Modified", "value": files_text, "inline": False})

    commits = payload.get("commits_created", [])
    if commits:
        commit_text = "\n".join(f"• `{c.get('sha', 'unknown')[:7]}` {c.get('message', '')[:60]}" for c in commits[:5])
        emb["fields"].append({"name": "Commits", "value": commit_text, "inline": False})

    emb["timestamp"] = payload.get("timestamp")
    emb["footer"] = {"text": f"Session ID: {session_id}"}

    await _post_to_discord_thread(thread_id, embeds=[emb])

    # Clean up thread tracking
    _session_threads.pop(session_id, None)
    logger.info("claude_session_ended", extra={"session_id": session_id, "end_reason": end_reason})


@app.post("/publish")
async def publish_test(body: Dict[str, Any] = Body(...)):
    """Test endpoint for publishing messages to Discord webhook."""
    content = body.get("content") or "PMOVES test message"
    embeds = body.get("embeds")
    raw_file = body.get("file")
    file_obj = _decode_publish_file(raw_file)
    if raw_file is not None and file_obj is None:
        raise HTTPException(400, "invalid file payload (expected base64 content)")
    if _nc is None:
        logger.warning(
            "nats_publish_skipped",
            extra={"event": "nats_publish_skipped", "reason": "nats_client_none"},
        )
    if file_obj:
        ok = await _post_discord_with_file(
            content,
            embeds,
            file_name=file_obj["name"],
            file_bytes=file_obj["bytes"],
            file_content_type=file_obj["content_type"],
        )
    else:
        ok = await _post_discord(content, embeds)
    if not ok:
        raise HTTPException(502, "discord webhook failed")
    return {"ok": True}
