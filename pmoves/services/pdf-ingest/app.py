import asyncio
import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import fitz  # type: ignore
import requests
from fastapi import Body, FastAPI, HTTPException
from minio import Minio
from nats.aio.client import Client as NATS
from pydantic import BaseModel

try:
    from services.common.events import envelope  # type: ignore
except Exception:  # pragma: no cover - fallback for local runs without shared module
    import datetime
    import uuid

    def envelope(topic: str, payload: dict, correlation_id: str | None = None, parent_id: str | None = None, source: str = "pdf-ingest") -> dict:
        env = {
            "id": str(uuid.uuid4()),
            "topic": topic,
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "version": "v1",
            "source": source,
            "payload": payload,
        }
        if correlation_id:
            env["correlation_id"] = correlation_id
        if parent_id:
            env["parent_id"] = parent_id
        return env

from libs.langextract import extract_text

logger = logging.getLogger(__name__)

app = FastAPI(title="PMOVES PDF Ingest", version="0.1.0")

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"
DEFAULT_BUCKET = os.environ.get("PDF_DEFAULT_BUCKET", os.environ.get("YT_BUCKET", "assets"))
DEFAULT_NAMESPACE = os.environ.get("PDF_DEFAULT_NAMESPACE", os.environ.get("INDEXER_NAMESPACE", "pmoves"))
EXTRACT_URL = (
    os.environ.get("PDF_INGEST_EXTRACT_URL")
    or os.environ.get("EXTRACT_PUBLISH_URL")
    or os.environ.get("EXTRACT_WORKER_URL")
    or "http://extract-worker:8083/ingest"
)
PDF_MAX_PAGES = int(os.environ.get("PDF_MAX_PAGES", "0"))
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

_nc: Optional[NATS] = None
_nats_supervisor: Optional[asyncio.Task[None]] = None


async def _nats_connect_loop() -> None:
    """Background task that maintains a NATS connection with retry backoff."""

    backoff = 1.0

    while True:
        client = NATS()

        async def _disconnected_cb() -> None:
            global _nc

            if _nc is client:
                logger.warning("NATS disconnected; events will be dropped until reconnection")
                _nc = None

        async def _reconnected_cb() -> None:
            global _nc

            logger.info("Reconnected to NATS at %s", NATS_URL)
            _nc = client

        async def _closed_cb() -> None:
            global _nc

            if _nc is client:
                logger.warning("NATS connection closed; restarting connection attempts")
                _nc = None

        try:
            await client.connect(
                servers=[NATS_URL],
                disconnected_cb=_disconnected_cb,
                reconnected_cb=_reconnected_cb,
                closed_cb=_closed_cb,
            )
        except asyncio.CancelledError:
            await client.close()
            raise
        except Exception as exc:
            logger.warning("Unable to connect to NATS at %s: %s", NATS_URL, exc)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
            continue

        logger.info("Connected to NATS at %s", NATS_URL)

        global _nc
        _nc = client
        backoff = 1.0

        try:
            await client.closed_future
        except asyncio.CancelledError:
            await client.close()
            raise
        finally:
            if _nc is client:
                _nc = None

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 30.0)


class PDFIngestRequest(BaseModel):
    key: str
    bucket: Optional[str] = None
    namespace: Optional[str] = None
    doc_id: Optional[str] = None
    title: Optional[str] = None
    file_id: Optional[str] = None
    publish_events: Optional[bool] = True


@app.on_event("startup")
async def startup() -> None:
    global _nats_supervisor

    if _nats_supervisor is None or _nats_supervisor.done():
        loop = asyncio.get_running_loop()
        _nats_supervisor = loop.create_task(_nats_connect_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    global _nats_supervisor

    if _nats_supervisor is not None:
        _nats_supervisor.cancel()
        try:
            await _nats_supervisor
        except asyncio.CancelledError:
            pass
        _nats_supervisor = None

    if _nc is not None:
        try:
            await _nc.close()
        except Exception:
            pass


def _minio_client() -> Minio:
    endpoint = MINIO_ENDPOINT
    if "://" in endpoint:
        endpoint = endpoint.split("//", 1)[1]
    return Minio(endpoint, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=MINIO_SECURE)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return slug or "document"


def _publish_event(topic: str, payload: Dict[str, Any]) -> None:
    if _nc is None:
        logger.warning(
            "Dropping event %s because NATS connection is unavailable; payload=%s",
            topic,
            payload,
        )
        return
    try:
        msg = envelope(topic, payload, source="pdf-ingest")
    except Exception:
        return
    asyncio.create_task(_nc.publish(topic, json.dumps(msg).encode()))


def _read_pdf_bytes(bucket: str, key: str) -> bytes:
    client = _minio_client()
    try:
        response = client.get_object(bucket, key)
        try:
            data = response.read()
        finally:
            response.close()
            response.release_conn()
    except Exception as exc:  # pragma: no cover - network failure
        raise HTTPException(status_code=502, detail=f"Failed to download s3://{bucket}/{key}: {exc}")
    if not data:
        raise HTTPException(status_code=422, detail="Downloaded PDF is empty")
    return data


def _pdf_to_text(data: bytes) -> str:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # pragma: no cover - parsing failure
        raise HTTPException(status_code=422, detail=f"Unable to open PDF: {exc}")
    try:
        texts: List[str] = []
        for idx, page in enumerate(doc):
            if PDF_MAX_PAGES and idx >= PDF_MAX_PAGES:
                break
            txt = page.get_text("text")
            if txt:
                texts.append(txt.strip())
    finally:
        doc.close()
    if not texts:
        raise HTTPException(status_code=422, detail="No extractable text found in PDF")
    return "\n\n".join(t for t in texts if t)


@app.get("/healthz")
def healthz() -> Dict[str, bool]:
    return {"ok": True}


@app.post("/pdf/ingest")
def ingest_pdf(body: PDFIngestRequest = Body(...)) -> Dict[str, Any]:
    bucket = body.bucket or DEFAULT_BUCKET
    namespace = body.namespace or DEFAULT_NAMESPACE
    if not body.key:
        raise HTTPException(status_code=400, detail="key is required")
    data = _read_pdf_bytes(bucket, body.key)
    checksum = hashlib.sha256(data).hexdigest()
    size_bytes = len(data)
    doc_base = body.doc_id or f"pdf:{_slugify(os.path.splitext(os.path.basename(body.key))[0])}"
    file_id = body.file_id or doc_base
    text = _pdf_to_text(data)
    extracted = extract_text(text, namespace=namespace, doc_id=doc_base)
    chunks = extracted.get("chunks") or []
    errors = extracted.get("errors") or []

    for idx, chunk in enumerate(chunks):
        chunk.setdefault("doc_id", doc_base)
        chunk.setdefault("namespace", namespace)
        if not chunk.get("chunk_id"):
            chunk["chunk_id"] = f"{doc_base}:{idx}"
        payload = chunk.get("payload") or {}
        if "source" not in payload:
            payload["source"] = "pdf"
        chunk["payload"] = payload

    ingest_payload = {"chunks": chunks, "errors": errors}
    try:
        resp = requests.post(EXTRACT_URL, headers={"content-type": "application/json"}, data=json.dumps(ingest_payload), timeout=60)
        resp.raise_for_status()
        ingest_result = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"status": resp.status_code}
    except Exception as exc:  # pragma: no cover - network failure
        raise HTTPException(status_code=502, detail=f"extract-worker ingest failed: {exc}")

    uri = f"s3://{bucket}/{body.key}"
    if body.publish_events:
        meta = {"namespace": namespace, "doc_id": doc_base}
        if body.title:
            meta["title"] = body.title
        file_event = {
            "file_id": file_id,
            "uri": uri,
            "kind": "document",
            "checksum": checksum,
            "size_bytes": size_bytes,
            "meta": meta,
        }
        _publish_event("ingest.file.added.v1", file_event)
        doc_event = {
            "doc_id": doc_base,
            "namespace": namespace,
            "uri": uri,
            "chunk_count": len(chunks),
            "file_id": file_id,
            "title": body.title,
            "checksum": checksum,
            "size_bytes": size_bytes,
            "preview": (chunks[0].get("text") or "")[:240] if chunks else "",
        }
        if errors:
            doc_event["meta"] = {"errors": len(errors)}
        _publish_event("ingest.document.ready.v1", doc_event)

    return {
        "ok": True,
        "doc_id": doc_base,
        "file_id": file_id,
        "uri": uri,
        "chunks": len(chunks),
        "errors": len(errors),
        "ingest": ingest_result,
    }
