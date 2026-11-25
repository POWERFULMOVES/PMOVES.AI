"""drop-folder-ingest service: polls a host drop folder, uploads to MinIO,
publishes ``ingest.file.added.v1`` for watch-folder-router to route.

The rules live in ``drop_ingest.py`` (stdlib only, unit-tested). This module
wires the real MinIO client and NATS connection into them and exposes
health/metrics. No models, no GPU, no egress.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from drop_ingest import SUBJECT, Config, DropFolderIngestor

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("drop-folder-ingest")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"
PMOVES_CONTRACTS_DIR = Path(os.environ.get("PMOVES_CONTRACTS_DIR", "/app/contracts"))

CONFIG = Config.from_env()

files_total = Counter("drop_folder_ingest_files_total", "Dropped files by outcome", ["outcome"])
bytes_total = Counter("drop_folder_ingest_bytes_total", "Bytes uploaded from the drop folder")
pending_gauge = Gauge("drop_folder_ingest_pending", "Files seen but not yet stable/processed")
folder_ok_gauge = Gauge("drop_folder_ingest_folder_ok", "1 when the drop folder is mounted and writable")

_nc = None
_minio = None
_buckets_ready: set = set()
_validator = None
_ingestor: Optional[DropFolderIngestor] = None
_task: Optional[asyncio.Task] = None


# ── contract validation (fail before the bus, not after) ─────────────────────
def _load_validator():
    """Validate payloads against the registered file-added.v1 schema when the
    contracts are present in the image (the Dockerfile copies them)."""
    schema_path = PMOVES_CONTRACTS_DIR / "schemas" / "ingest" / "file-added.v1.schema.json"
    try:
        import jsonschema

        schema = json.loads(schema_path.read_text())
        return jsonschema.Draft202012Validator(schema)
    except Exception:  # noqa: BLE001
        logger.warning("file-added.v1 schema not loadable from %s; publishing unvalidated", schema_path)
        return None


# ── MinIO ────────────────────────────────────────────────────────────────────
def _minio_client():
    from minio import Minio

    endpoint = MINIO_ENDPOINT.split("//", 1)[1] if "://" in MINIO_ENDPOINT else MINIO_ENDPOINT
    return Minio(endpoint, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=MINIO_SECURE)


def _ensure_bucket(client, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("created bucket %s", bucket)


def _upload(bucket: str, key: str, path: Path, content_type: str, sha256: str) -> None:
    global _minio
    if _minio is None:
        _minio = _minio_client()
    if bucket not in _buckets_ready:
        _ensure_bucket(_minio, bucket)
        _buckets_ready.add(bucket)
    _minio.fput_object(
        bucket, key, str(path), content_type=content_type,
        metadata={"sha256": sha256, "source": "drop-folder"},
    )


# ── NATS ─────────────────────────────────────────────────────────────────────
def _nats_connected() -> bool:
    return _nc is not None and _nc.is_connected


async def _publish(subject: str, data: bytes) -> None:
    if _validator is not None:
        _validator.validate(json.loads(data)["payload"])
    if not _nats_connected():
        raise RuntimeError("NATS not connected")
    await _nc.publish(subject, data)
    await _nc.flush(timeout=5)


async def _poll_loop() -> None:
    assert _ingestor is not None
    while True:
        try:
            summary = await _ingestor.scan_once(can_publish=_nats_connected())
            folder_ok_gauge.set(1 if summary["drop_folder_ok"] else 0)
            pending_gauge.set(summary["pending"])
            for outcome in ("published", "duplicate", "failed", "retry"):
                if summary[outcome]:
                    files_total.labels(outcome=outcome).inc(summary[outcome])
        except Exception:  # noqa: BLE001 - the loop must survive anything
            logger.exception("poll cycle failed")
        await asyncio.sleep(CONFIG.poll_interval)


# ── lifespan / app ───────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _nc, _validator, _ingestor, _task
    _validator = _load_validator()
    try:
        import nats

        _nc = await nats.connect(NATS_URL, max_reconnect_attempts=-1)
        logger.info("NATS connected")
    except Exception:  # noqa: BLE001
        logger.exception("NATS connect failed; files wait in the drop folder until it is reachable")
        _nc = None

    def _upload_counted(bucket, key, path, content_type, sha256):
        _upload(bucket, key, path, content_type, sha256)
        bytes_total.inc(path.stat().st_size)

    _ingestor = DropFolderIngestor(CONFIG, upload=_upload_counted, publish=_publish)
    _task = asyncio.create_task(_poll_loop())
    logger.info("watching %s every %.1fs -> s3://%s/%s/", CONFIG.drop_dir, CONFIG.poll_interval,
                CONFIG.bucket, CONFIG.key_prefix)
    yield
    _task.cancel()
    if _nc is not None:
        await _nc.drain()


app = FastAPI(title="drop-folder-ingest", lifespan=lifespan)


@app.get("/healthz")
async def healthz(response: Response) -> Dict[str, Any]:
    ok = _ingestor is not None and _ingestor.drop_folder_ok()
    if not ok:
        # Unhealthy on a missing/unwritable mount (e.g. the archive drive was
        # unplugged): that is the failure an operator needs to see.
        response.status_code = 503
    return {
        "status": "healthy" if ok else "unhealthy",
        "service": "drop-folder-ingest",
        "drop_folder": str(CONFIG.drop_dir),
        "drop_folder_ok": ok,
        "nats_connected": _nats_connected(),
        "bucket": CONFIG.bucket,
        "key_prefix": CONFIG.key_prefix,
        "publishes": SUBJECT,
        "schema_validation": _validator is not None,
        "last_scan": _ingestor.last_scan if _ingestor else None,
        "last_error": _ingestor.last_error if _ingestor else None,
        "totals": _ingestor.totals if _ingestor else {},
    }


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
