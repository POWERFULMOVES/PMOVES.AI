"""
Messaging Gateway Service
Unified API for Discord, Telegram, and WhatsApp notifications with interactive buttons.
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from nats.aio.client import Client as NATS
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, REGISTRY

from platforms.discord import DiscordPlatform
from platforms.telegram import TelegramPlatform
from platforms.whatsapp import WhatsAppPlatform


YOUTUBE_CONTROL_REJECTION_LABELS = {
    "policy": "Policy issue",
    "scope": "Out of scope",
    "revise": "Needs revision",
    "other": "Rejected",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global _nats_loop_task

    # Startup
    logger.info("Starting messaging gateway...")

    # Initialize platform handlers
    await discord_platform.initialize()
    await telegram_platform.initialize()
    await whatsapp_platform.initialize()

    # Start NATS loop
    _nats_loop_task = asyncio.create_task(_nats_resilience_loop())
    logger.info("Messaging gateway started")

    yield

    # Shutdown
    global _nc
    if _nats_loop_task:
        _nats_loop_task.cancel()
        try:
            await _nats_loop_task
        except asyncio.CancelledError:
            pass
        _nats_loop_task = None

    if _nc:
        await _nc.close()
        _nc = None

    logger.info("Messaging gateway shut down")


app = FastAPI(title="Messaging Gateway", version="0.1.0", lifespan=lifespan)

# Environment configuration
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_APPLICATION_ID = os.environ.get("DISCORD_APPLICATION_ID", "")
DISCORD_PUBLIC_KEY = os.environ.get("DISCORD_PUBLIC_KEY", "")
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
CHANNEL_MONITOR_URL = os.environ.get("CHANNEL_MONITOR_URL", "http://channel-monitor:8097")
CHANNEL_MONITOR_SECRET = os.environ.get("CHANNEL_MONITOR_SECRET", "")

# NATS subjects to subscribe to for auto-forwarding
SUBJECTS = os.environ.get(
    "MESSAGING_SUBJECTS",
    "ingest.file.added.v1,ingest.transcript.ready.v1,ingest.summary.ready.v1,ingest.chapters.ready.v1",
).split(",")

logger = logging.getLogger("messaging_gateway")
logging.basicConfig(level=logging.INFO)

_nc: Optional[NATS] = None
_nats_loop_task: Optional[asyncio.Task] = None

# Initialize platform handlers
discord_platform = DiscordPlatform(
    webhook_url=DISCORD_WEBHOOK_URL,
    application_id=DISCORD_APPLICATION_ID,
    public_key=DISCORD_PUBLIC_KEY,
)
telegram_platform = TelegramPlatform(bot_token=TELEGRAM_BOT_TOKEN)
whatsapp_platform = WhatsAppPlatform(access_token=WHATSAPP_ACCESS_TOKEN)

# Prometheus metrics
messages_sent = Counter(
    'messaging_gateway_messages_sent_total',
    'Total number of messages sent to platforms',
    ['platform', 'status']
)
nats_messages_received = Counter(
    'messaging_gateway_nats_messages_received_total',
    'Total number of messages received from NATS',
    ['subject']
)
api_requests = Counter(
    'messaging_gateway_api_requests_total',
    'Total number of API requests',
    ['endpoint', 'status']
)
request_duration = Histogram(
    'messaging_gateway_request_duration_seconds',
    'Request processing duration',
    ['endpoint']
)


class SendMessageRequest(BaseModel):
    """Request model for unified send endpoint."""
    platforms: list[str]  # e.g., ["discord", "telegram", "whatsapp"]
    content: str
    embeds: Optional[list[dict]] = None
    buttons: Optional[list[dict]] = None  # Platform-agnostic button definitions
    metadata: Optional[dict] = None


def _interaction_actor(payload: Dict[str, Any]) -> str:
    """Extract a ``username:id`` actor string from a Discord interaction payload."""
    member = payload.get("member") if isinstance(payload.get("member"), dict) else {}
    user = member.get("user") if isinstance(member.get("user"), dict) else payload.get("user", {})
    username = user.get("username") if isinstance(user, dict) else None
    user_id = user.get("id") if isinstance(user, dict) else None
    if username and user_id:
        return f"{username}:{user_id}"
    if user_id:
        return str(user_id)
    return "discord-user"


def _format_ytcontrol_response(body: Dict[str, Any], action_id: str, approve: bool) -> str:
    """Format a YouTube control review result into a Discord-friendly message."""
    actions = body.get("actions") if isinstance(body.get("actions"), list) else []
    first_action = actions[0] if actions and isinstance(actions[0], dict) else {}
    summary = first_action.get("summary")
    notebook_entry_id = first_action.get("notebook_entry_id")
    request_source = first_action.get("request_source")
    source_class = first_action.get("source_class")
    target_ref = first_action.get("target_ref")
    reason_code = body.get("reason_code") or first_action.get("reason_code")
    reason = body.get("reason")
    state = "Approved" if approve else "Rejected"
    parts = [f"{state} YouTube control request `{action_id}`."]
    if summary:
        parts.append(str(summary))
    context_parts = []
    if request_source:
        context_parts.append(f"source `{request_source}`")
    if source_class:
        context_parts.append(f"class `{source_class}`")
    if target_ref:
        context_parts.append(f"target `{target_ref}`")
    if context_parts:
        parts.append("Context: " + ", ".join(context_parts) + ".")
    if reason_code and not approve:
        parts.append(f"Reason type: {YOUTUBE_CONTROL_REJECTION_LABELS.get(str(reason_code), str(reason_code))}.")
    if reason:
        parts.append(f"Note: {reason}")
    if notebook_entry_id:
        parts.append(f"Notebook: `{notebook_entry_id}`")
    parts.append(f"Processed: {body.get('processed', 0)}.")
    return " ".join(parts)


async def _handle_ytcontrol_interaction(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle a Discord button interaction for YouTube control approve/reject."""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    custom_id = data.get("custom_id")
    if not isinstance(custom_id, str) or not custom_id.startswith("ytcontrol:"):
        return None

    parts = custom_id.split(":")
    if len(parts) not in {3, 4}:
        return {
            "type": 4,
            "data": {"content": "Invalid YouTube control action id.", "flags": 64},
        }
    _, action, action_id, *tail = parts
    approve = action == "approve"
    if action not in {"approve", "reject"}:
        return {
            "type": 4,
            "data": {"content": f"Unsupported YouTube control action: {action}", "flags": 64},
        }
    reason_code = tail[0] if tail else None
    if reason_code and reason_code not in YOUTUBE_CONTROL_REJECTION_LABELS:
        return {
            "type": 4,
            "data": {"content": f"Unsupported YouTube control reject reason: {reason_code}", "flags": 64},
        }

    headers = {"content-type": "application/json"}
    if CHANNEL_MONITOR_SECRET:
        headers["X-Channel-Monitor-Token"] = CHANNEL_MONITOR_SECRET
    reason = "approved from Discord" if approve else "rejected from Discord"
    if reason_code and not approve:
        reason = f"{reason} ({YOUTUBE_CONTROL_REJECTION_LABELS[reason_code].lower()})"
    review_payload = {
        "action_ids": [action_id],
        "approve": approve,
        "actor": _interaction_actor(payload),
        "reason": reason,
        "reason_code": reason_code,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{CHANNEL_MONITOR_URL.rstrip('/')}/api/monitor/youtube-control/review",
                headers=headers,
                json=review_payload,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"channel-monitor returned {exc.response.status_code}: "
                    f"{exc.response.text[:500]}"
                ) from exc
            body = response.json()
    except Exception as exc:
        logger.warning("YouTube control Discord interaction failed for %s: %s", action_id, exc)
        return {
            "type": 4,
            "data": {"content": f"Review action failed for {action_id}", "flags": 64},
        }

    content = _format_ytcontrol_response(body, action_id, approve)
    return {
        "type": 4,
        "data": {"content": content, "flags": 64},
    }


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {
        "ok": True,
        "platforms": {
            "discord": discord_platform.is_configured(),
            "telegram": telegram_platform.is_configured(),
            "whatsapp": whatsapp_platform.is_configured(),
        },
        "nats_connected": _nc is not None and _nc.is_connected,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from fastapi.responses import Response
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/send")
async def send_message(request: SendMessageRequest):
    """
    Unified send endpoint for all platforms.

    Example:
    {
        "platforms": ["discord", "telegram"],
        "content": "New content ready for approval",
        "buttons": [
            {"id": "approve_123", "label": "Approve", "style": "primary"},
            {"id": "reject_123", "label": "Reject", "style": "danger"}
        ]
    }
    """
    api_requests.labels("/v1/send", "started").inc()
    results = {}

    for platform in request.platforms:
        if platform == "discord":
            success = await discord_platform.send(
                content=request.content,
                embeds=request.embeds,
                buttons=request.buttons,
            )
            results["discord"] = {"success": success}
            messages_sent.labels("discord", "success" if success else "failed").inc()
        elif platform == "telegram":
            success = await telegram_platform.send(
                content=request.content,
                buttons=request.buttons,
            )
            results["telegram"] = {"success": success}
            messages_sent.labels("telegram", "success" if success else "failed").inc()
        elif platform == "whatsapp":
            success = await whatsapp_platform.send(
                content=request.content,
                buttons=request.buttons,
            )
            results["whatsapp"] = {"success": success}
            messages_sent.labels("whatsapp", "success" if success else "failed").inc()
        else:
            results[platform] = {"success": False, "error": "unknown_platform"}
            messages_sent.labels("unknown", "failed").inc()

    # Return 200 if at least one platform succeeded
    any_success = any(r.get("success", False) for r in results.values())
    if not any_success:
        api_requests.labels("/v1/send", "failed").inc()
        raise HTTPException(status_code=502, detail="All platforms failed")

    api_requests.labels("/v1/send", "success").inc()
    return {"ok": True, "results": results}


@app.post("/webhooks/discord")
async def discord_webhook(request: Request):
    """Handle Discord interaction callbacks (button clicks).

    Validates Ed25519 signature before processing per Discord requirements.
    See: https://discord.com/developers/docs/interactions/receiving-and-responding
    """
    # Get raw body and signature headers
    body = await request.body()
    signature = request.headers.get("X-Signature-Ed25519", "")
    timestamp = request.headers.get("X-Signature-Timestamp", "")

    # Verify signature (required by Discord)
    if not discord_platform.verify_signature(signature, timestamp, body):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse and handle interaction
    payload = await request.json()

    # Handle ping (type 1) for Discord URL verification
    if payload.get("type") == 1:
        return {"type": 1}

    ytcontrol_response = await _handle_ytcontrol_interaction(payload)
    if ytcontrol_response is not None:
        return ytcontrol_response

    return await discord_platform.handle_interaction(payload)


@app.post("/webhooks/telegram")
async def telegram_webhook(payload: dict):
    """Handle Telegram bot updates (button callbacks, commands)."""
    return await telegram_platform.handle_update(payload)


async def _handle_nats_message(msg):
    """Handle NATS events and auto-forward to configured platforms."""
    nats_messages_received.labels(msg.subject).inc()
    try:
        data = json.loads(msg.data.decode("utf-8"))
        envelope: Dict[str, Any] = data if isinstance(data, dict) else {}
    except Exception:
        logger.warning(f"Failed to parse NATS message from {msg.subject}")
        return

    subject = envelope.get("topic") or msg.subject
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else envelope or {}

    logger.info(f"Received NATS event: {subject}")

    # Format notification based on event type
    content = _format_notification(subject, payload)

    # Auto-forward to all configured platforms
    platforms = []
    if discord_platform.is_configured():
        platforms.append("discord")
    if telegram_platform.is_configured():
        platforms.append("telegram")

    if platforms:
        try:
            await send_message(SendMessageRequest(
                platforms=platforms,
                content=content,
                metadata={"subject": subject, "payload": payload}
            ))
        except Exception as e:
            logger.error(f"Failed to forward NATS event to platforms: {e}")


def _format_notification(subject: str, payload: dict) -> str:
    """Format NATS event into human-readable notification."""
    if subject == "ingest.file.added.v1":
        title = payload.get("title") or payload.get("key")
        return f"📥 New file ingested: {title}"
    elif subject == "ingest.transcript.ready.v1":
        video_id = payload.get("video_id")
        return f"📝 Transcript ready: {video_id}"
    elif subject == "ingest.summary.ready.v1":
        video_id = payload.get("video_id")
        return f"📊 Summary generated: {video_id}"
    elif subject == "ingest.chapters.ready.v1":
        video_id = payload.get("video_id")
        chapters = payload.get("chapters", [])
        return f"🎬 Chapters created: {video_id} ({len(chapters)} chapters)"
    else:
        return f"🔔 Event: {subject}"


async def _register_nats_subscriptions(nc: NATS) -> None:
    """Subscribe to configured NATS subjects."""
    subjects = [subj.strip() for subj in SUBJECTS if subj.strip()]

    for subj in subjects:
        try:
            await nc.subscribe(subj, cb=_handle_nats_message)
            logger.info(f"Subscribed to NATS subject: {subj}")
        except Exception as exc:
            logger.warning(f"Failed to subscribe to {subj}: {exc}")


async def _nats_resilience_loop() -> None:
    """Maintain resilient NATS connection with auto-reconnect."""
    global _nc
    backoff = 1.0

    while True:
        nc = NATS()
        disconnect_event = asyncio.Event()

        async def _disconnected_cb():
            if not disconnect_event.is_set():
                disconnect_event.set()
            logger.warning("NATS connection lost")

        async def _closed_cb():
            if not disconnect_event.is_set():
                disconnect_event.set()
            logger.warning("NATS connection closed")

        try:
            logger.info(f"Connecting to NATS at {NATS_URL}...")
            await nc.connect(
                servers=[NATS_URL],
                disconnected_cb=_disconnected_cb,
                closed_cb=_closed_cb,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"NATS connect failed: {exc}, retrying in {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)
            continue

        _nc = nc
        backoff = 1.0
        logger.info("NATS connected")

        await _register_nats_subscriptions(nc)

        try:
            await disconnect_event.wait()
        except asyncio.CancelledError:
            await nc.close()
            if _nc is nc:
                _nc = None
            raise

        await nc.close()

    logger.info("Messaging gateway stopped")
