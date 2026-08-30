"""
Replay Compressor Service
=========================
Listens for owner presence events. When the owner is absent for a sustained
period, sealed replay records are compressed and uploaded to JuiceFS (via the
S3 gateway). When the owner returns, records are restored.

Pattern follows pmoves/services/semantic-cache/main.py.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
import httpx
import uvicorn
from botocore.client import Config
from fastapi import FastAPI
from nats.aio.client import Client as NATSClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://juicefs-gateway:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "pmoves")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "pmoves-secret")
S3_BUCKET = os.getenv("S3_BUCKET", "pmoves-sealed")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
SECONDS_BEFORE_COMPRESS = int(os.getenv("SECONDS_BEFORE_COMPRESS", "300"))
RECORDS_API = os.getenv("RECORDS_API", "http://records-service:8080")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Subjects
SUBJECT_ABSENT = "owner.presence.absent.v1"
SUBJECT_DETECTED = "owner.presence.detected.v1"
SUBJECT_COMPRESSED = "sealed.record.compressed.v1"
SUBJECT_RESTORED = "sealed.record.restored.v1"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("replay-compressor")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

# Maps record_id -> asyncio.Task for in-flight compression waits
_pending: Dict[str, asyncio.Task] = {}

# ---------------------------------------------------------------------------
# S3 client (JuiceFS gateway, NOT MinIO)
# ---------------------------------------------------------------------------

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION,
    config=Config(signature_version="s3v4"),
)


def ensure_bucket() -> None:
    try:
        s3.head_bucket(Bucket=S3_BUCKET)
    except Exception:
        try:
            s3.create_bucket(Bucket=S3_BUCKET)
            log.info("created bucket %s", S3_BUCKET)
        except Exception as exc:
            log.warning("ensure_bucket failed: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def fetch_sealed_records(record_id: Optional[str] = None) -> Dict[str, Any]:
    """Fetch sealed replay records from the records service."""
    url = f"{RECORDS_API}/api/v1/sealed"
    if record_id:
        url = f"{url}/{record_id}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.warning("fetch_sealed_records failed: %s", exc)
        return {}


def upload_payload(key: str, payload: bytes) -> bool:
    """Upload compressed payload to JuiceFS bucket."""
    try:
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=payload)
        log.info("uploaded s3://%s/%s (%d bytes)", S3_BUCKET, key, len(payload))
        return True
    except Exception as exc:
        log.warning("upload_payload failed: %s", exc)
        return False


def restore_payload(key: str) -> Optional[bytes]:
    """Download payload from JuiceFS bucket."""
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        data = obj["Body"].read()
        log.info("restored s3://%s/%s (%d bytes)", S3_BUCKET, key, len(data))
        return data
    except Exception as exc:
        log.warning("restore_payload failed: %s", exc)
        return None


async def publish(nc: NATSClient, subject: str, data: Dict[str, Any]) -> None:
    try:
        await nc.publish(subject, json.dumps(data).encode())
        log.info("published %s", subject)
    except Exception as exc:
        log.warning("publish %s failed: %s", subject, exc)


# ---------------------------------------------------------------------------
# Compression lifecycle
# ---------------------------------------------------------------------------


async def compress_after_delay(nc: NATSClient, record_id: str) -> None:
    """Wait the configured grace period, then compress and seal the record."""
    try:
        log.info(
            "scheduling compression for %s in %ds", record_id, SECONDS_BEFORE_COMPRESS
        )
        await asyncio.sleep(SECONDS_BEFORE_COMPRESS)
        data = await fetch_sealed_records(record_id)
        if not data:
            log.warning("no records returned for %s, skipping", record_id)
            return
        payload = json.dumps(data, sort_keys=True).encode()
        key = f"{record_id}.json"
        if upload_payload(key, payload):
            await publish(
                nc,
                SUBJECT_COMPRESSED,
                {
                    "record_id": record_id,
                    "sealed_at": _now_iso(),
                    "bytes": len(payload),
                    "uri": f"s3://{S3_BUCKET}/{key}",
                },
            )
    except asyncio.CancelledError:
        log.info("compression cancelled for %s", record_id)
        raise
    except Exception as exc:
        log.warning("compress_after_delay error for %s: %s", record_id, exc)
    finally:
        _pending.pop(record_id, None)


async def handle_restore(nc: NATSClient, record_id: str) -> None:
    try:
        key = f"{record_id}.json"
        data = restore_payload(key)
        if data is not None:
            await publish(
                nc,
                SUBJECT_RESTORED,
                {
                    "record_id": record_id,
                    "restored_at": _now_iso(),
                    "bytes": len(data),
                    "uri": f"s3://{S3_BUCKET}/{key}",
                },
            )
    except Exception as exc:
        log.warning("handle_restore error for %s: %s", record_id, exc)


# ---------------------------------------------------------------------------
# NATS message handlers
# ---------------------------------------------------------------------------


async def on_absent(msg) -> None:
    try:
        payload = json.loads(msg.data or b"{}")
        record_id = payload.get("record_id") or payload.get("id")
        if not record_id:
            log.warning("absent event without record_id: %s", payload)
            return
        if record_id in _pending:
            _pending[record_id].cancel()
        task = asyncio.create_task(compress_after_delay(nc_app, record_id))
        _pending[record_id] = task
    except Exception as exc:
        log.warning("on_absent error: %s", exc)


async def on_detected(msg) -> None:
    try:
        payload = json.loads(msg.data or b"{}")
        record_id = payload.get("record_id") or payload.get("id")
        if not record_id:
            log.warning("detected event without record_id: %s", payload)
            return
        task = _pending.pop(record_id, None)
        if task and not task.done():
            task.cancel()
            log.info("cancelled pending compression for %s", record_id)
        await handle_restore(nc_app, record_id)
    except Exception as exc:
        log.warning("on_detected error: %s", exc)


# ---------------------------------------------------------------------------
# FastAPI lifecycle
# ---------------------------------------------------------------------------

nc_app: NATSClient = NATSClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global nc_app
    nc_app = NATSClient()
    try:
        await nc_app.connect(NATS_URL, name="replay-compressor")
        log.info("connected to NATS %s", NATS_URL)
        await nc_app.subscribe(SUBJECT_ABSENT, cb=on_absent)
        await nc_app.subscribe(SUBJECT_DETECTED, cb=on_detected)
        log.info("subscribed to %s and %s", SUBJECT_ABSENT, SUBJECT_DETECTED)
    except Exception as exc:
        log.warning("NATS connect failed (fail-open): %s", exc)
    try:
        ensure_bucket()
    except Exception as exc:
        log.warning("ensure_bucket at startup failed: %s", exc)
    yield
    try:
        await nc_app.drain()
    except Exception:
        pass


app = FastAPI(title="PMOVES Replay Compressor", lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "nats_connected": nc_app.is_connected,
        "pending_compressions": len(_pending),
        "bucket": S3_BUCKET,
        "endpoint": S3_ENDPOINT_URL,
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8080, log_level="info")
