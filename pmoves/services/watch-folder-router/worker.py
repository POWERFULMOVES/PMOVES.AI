"""watch-folder-router — SEAP ingestion Bud 1 (constellation map 2026-08-12).

Consumes `ingest.file.added.v1` (emitted when a file lands in MinIO — the
watch-folder ingestion point) and routes it to the right analyzer by MIME type,
publishing the appropriate downstream "ready" subject so the rest of the
constellation (transcript-harvester, extract-worker, archon-harvest) can pick
it up. This retires the manual `media-audio /analyze` calls that every
hand-driven ingest used to make.

Routing:
  audio/* , video/*        -> media-audio /analyze (transcription)
                              -> publish ingest.transcript.ready.v1
  application/pdf, docs*    -> publish ingest.document.ready.v1
                              (pdf-ingest / langextract consume it)
  everything else (text)    -> publish ingest.text.ready.v1
                              (extract-worker embeds it)

Thin orchestrator: no models, no GPU. Reuses the voice-sampler MinIO pattern
and the extract-worker fire-and-forget NATS-publish posture. HTTP surface is
health/metrics only — the work is NATS-driven.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests as http
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("watch-folder-router")

# ── Config ──────────────────────────────────────────────────────────────────
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
MEDIA_AUDIO_URL = os.environ.get("MEDIA_AUDIO_URL", "http://media-audio:8082")

SUBJECT_IN = "ingest.file.added.v1"
SUBJECT_TRANSCRIPT = "ingest.transcript.ready.v1"
SUBJECT_DOCUMENT = "ingest.document.ready.v1"
SUBJECT_TEXT = "ingest.text.ready.v1"

DIARIZE_TIMEOUT = int(os.environ.get("ROUTER_TRANSCRIBE_TIMEOUT_SEC", "3600"))
# Doc MIME types that pdf-ingest / langextract handle downstream.
DOC_MIME_PREFIXES = ("application/pdf",)
DOC_MIME_EXACT = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/rtf",
}

routed_total = Counter(
    "watch_folder_router_routed_total", "Files routed", ["route", "status"]
)

_nc = None


# ── Routing ─────────────────────────────────────────────────────────────────
def _classify(mime: str, key: str) -> str:
    """Return one of: 'media', 'document', 'text'."""
    mime = (mime or "").lower()
    if mime.startswith("audio/") or mime.startswith("video/"):
        return "media"
    if mime.startswith(DOC_MIME_PREFIXES) or mime in DOC_MIME_EXACT:
        return "document"
    # Fall back to extension when the MIME is generic (octet-stream).
    ext = os.path.splitext(key or "")[1].lower()
    if ext in (".m4a", ".mp3", ".wav", ".mp4", ".webm", ".mkv", ".mov", ".ogg", ".flac"):
        return "media"
    if ext in (".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".rtf"):
        return "document"
    return "text"


def _envelope(topic: str, payload: Dict[str, Any], src_event: Dict[str, Any]) -> bytes:
    return json.dumps(
        {
            "topic": topic,
            "payload": payload,
            "correlation_id": src_event.get("correlation_id") or src_event.get("file_id"),
            "source": "watch-folder-router",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()


def _transcribe(bucket: str, key: str) -> Dict[str, Any]:
    resp = http.post(
        f"{MEDIA_AUDIO_URL}/analyze",
        json={"bucket": bucket, "key": key, "analysis_type": "transcription"},
        timeout=DIARIZE_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


async def _handle_file_added(msg) -> None:
    try:
        event = json.loads(msg.data.decode())
    except Exception:  # noqa: BLE001
        logger.exception("unparseable ingest.file.added event")
        routed_total.labels(route="unknown", status="rejected").inc()
        return

    bucket = event.get("bucket")
    key = event.get("key")
    mime = event.get("mime_type", "")
    if not bucket or not key:
        logger.warning("event missing bucket/key: %s", event)
        routed_total.labels(route="unknown", status="rejected").inc()
        return

    route = _classify(mime, key)
    base = {
        "file_id": event.get("file_id"),
        "bucket": bucket,
        "key": key,
        "mime_type": mime,
        "namespace": event.get("namespace"),
        "room_id": event.get("room_id"),
        "persona": event.get("persona"),
        "uploader": event.get("uploader"),
    }

    try:
        if route == "media":
            # Transcription is the slow step; run it off the event-loop thread.
            body = await asyncio.to_thread(_transcribe, bucket, key)
            if body.get("error"):
                raise RuntimeError(f"media-audio error: {body['error']}")
            text = body.get("text") or ""
            payload = {
                **base,
                "text": text,
                "chunks": body.get("chunks", []),
                "model": body.get("model"),
                "char_count": len(str(text)),
            }
            await _publish(SUBJECT_TRANSCRIPT, payload, event)
            routed_total.labels(route="media", status="ok").inc()
            logger.info("routed media %s -> transcript.ready (%d chars)", key, len(str(text)))
        elif route == "document":
            # pdf-ingest / langextract own extraction; router only announces.
            await _publish(SUBJECT_DOCUMENT, base, event)
            routed_total.labels(route="document", status="ok").inc()
            logger.info("routed document %s -> document.ready", key)
        else:
            await _publish(SUBJECT_TEXT, base, event)
            routed_total.labels(route="text", status="ok").inc()
            logger.info("routed text %s -> text.ready", key)
    except Exception:  # noqa: BLE001
        logger.exception("routing failed for %s (route=%s)", key, route)
        routed_total.labels(route=route, status="error").inc()


async def _publish(topic: str, payload: Dict[str, Any], src_event: Dict[str, Any]) -> None:
    if _nc is None:
        logger.warning("NATS not connected; dropping %s for %s", topic, payload.get("key"))
        return
    await _nc.publish(topic, _envelope(topic, payload, src_event))


# ── Lifespan / app ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _nc
    try:
        import nats

        _nc = await nats.connect(NATS_URL, max_reconnect_attempts=-1)
        await _nc.subscribe(SUBJECT_IN, cb=_handle_file_added)
        logger.info("NATS connected; subscribed %s", SUBJECT_IN)
    except Exception:  # noqa: BLE001
        logger.exception("NATS connect failed — router is idle until NATS is reachable")
        _nc = None
    yield
    if _nc is not None:
        await _nc.drain()


app = FastAPI(title="watch-folder-router", lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    return {
        "status": "healthy",
        "service": "watch-folder-router",
        "nats_connected": _nc is not None and not _nc.is_closed,
        "media_audio_url": MEDIA_AUDIO_URL,
        "subscribes": SUBJECT_IN,
        "publishes": [SUBJECT_TRANSCRIPT, SUBJECT_DOCUMENT, SUBJECT_TEXT],
    }


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
