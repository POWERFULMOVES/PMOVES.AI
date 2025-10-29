import asyncio
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


app = FastAPI(title="Publisher-Discord", version="0.1.0")

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
# Prefer the n8n-style username if provided, fallback to legacy var
DISCORD_USERNAME = os.environ.get("DISCORD_USERNAME", os.environ.get("DISCORD_WEBHOOK_USERNAME", "PMOVES"))
DISCORD_AVATAR_URL = os.environ.get("DISCORD_AVATAR_URL", "")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
SUBJECTS = os.environ.get(
    "DISCORD_SUBJECTS",
    "ingest.file.added.v1,ingest.transcript.ready.v1,ingest.summary.ready.v1,ingest.chapters.ready.v1,content.published.v1",
).split(",")

JELLYFIN_URL = os.environ.get("JELLYFIN_URL", "")
# Default to the legacy style expected by tests; allow override.
DISCORD_PUBLISH_PREFIX = os.environ.get("DISCORD_PUBLISH_PREFIX", "Published: ")

DISCORD_METRICS_TABLE = os.environ.get("DISCORD_METRICS_TABLE", "publisher_discord_metrics")
DISCORD_METRICS_CONFLICT = os.environ.get("DISCORD_METRICS_CONFLICT", "published_event_id")


_nc: Optional[NATS] = None
_nats_loop_task: Optional[asyncio.Task] = None
_webhook_counters = Counter()
_telemetry_metrics = PublisherMetrics()
logger = logging.getLogger("publisher_discord")


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
    return {
        "ok": True,
        "webhook": bool(DISCORD_WEBHOOK_URL),
        "metrics": _webhook_snapshot(),
        "telemetry": _telemetry_metrics.summary(),
    }


@app.get("/metrics")
async def metrics():
    return {
        "webhook": _webhook_snapshot(),
        "telemetry": _telemetry_metrics.summary(),
    }

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

def _format_event(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    name = name.strip()
    emb = {"title": name, "fields": []}
    color_map = {
        "ingest.file.added.v1": 0x2b90d9,
        "ingest.transcript.ready.v1": 0x10b981,
        "ingest.summary.ready.v1": 0xf59e0b,
        "ingest.chapters.ready.v1": 0x8b5cf6,
        "content.published.v1": 0x22c55e,
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

@app.on_event("startup")
async def startup():
    global _nats_loop_task
    if _nats_loop_task and _nats_loop_task.done():
        try:
            _nats_loop_task.result()
        except Exception as exc:  # pragma: no cover - startup diagnostics
            logger.warning(
                "nats_loop_previous_failure",
                extra={"event": "nats_loop_previous_failure", "error": str(exc)},
            )
    if _nats_loop_task is None or _nats_loop_task.done():
        logger.info(
            "nats_loop_start",
            extra={"event": "nats_loop_start", "servers": [NATS_URL]},
        )
        _nats_loop_task = asyncio.create_task(_nats_resilience_loop())


@app.on_event("shutdown")
async def shutdown():
    global _nats_loop_task, _nc
    if _nats_loop_task:
        _nats_loop_task.cancel()
        with contextlib.suppress(Exception):
            await _nats_loop_task
        _nats_loop_task = None
    if _nc:
        with contextlib.suppress(Exception):
            await _nc.close()
        _nc = None

@app.post("/publish")
async def publish_test(body: Dict[str, Any] = Body(...)):
    content = body.get("content") or "PMOVES test message"
    embeds = body.get("embeds")
    if _nc is None:
        logger.warning(
            "nats_publish_skipped",
            extra={"event": "nats_publish_skipped", "reason": "nats_client_none"},
        )
    ok = await _post_discord(content, embeds)
    if not ok:
        raise HTTPException(502, "discord webhook failed")
    return {"ok": True}
