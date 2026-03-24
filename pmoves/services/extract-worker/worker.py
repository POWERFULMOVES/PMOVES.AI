import asyncio
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List

from fastapi import FastAPI, Body, HTTPException, Response
import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import numpy as np

# Prometheus metrics
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

http_requests_total = Counter('extract_worker_http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
http_request_duration = Histogram('extract_worker_http_request_duration_seconds', 'HTTP request duration')
qdrant_operations_total = Counter('extract_worker_qdrant_operations_total', 'Qdrant operations', ['operation'])
embeddings_processed_total = Counter('extract_worker_embeddings_processed_total', 'Embeddings processed')

QDRANT_URL = os.environ.get("QDRANT_URL","http://qdrant:6333")
COLL = os.environ.get("QDRANT_COLLECTION","pmoves_chunks_qwen3")
MODEL = os.environ.get("SENTENCE_MODEL","all-MiniLM-L6-v2")
MEILI_URL = os.environ.get("MEILI_URL","http://meilisearch:7700")
MEILI_API_KEY = os.environ.get("MEILI_API_KEY","")
SUPA = os.environ.get("SUPA_REST_URL","http://postgrest:3000")
EMBEDDING_BACKEND = os.environ.get("EMBEDDING_BACKEND", "sentence-transformers").lower()

# ── CHIT / NATS CGP publishing ───────────────────────────────────────────────
logger = logging.getLogger("pmoves.extract-worker")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
CGP_PUBLISH_ENABLED = os.environ.get(
    "EXTRACT_WORKER_CGP_PUBLISH", "true"
).lower() in ("1", "true", "yes")
CGP_SPEC_VERSION = "chit.cgp.v1.0"
CGP_SUBJECT = "tokenism.cgp.ready.v1"
SKILL_HOOK_SUBJECT = "skills.step.extract-worker.done.v1"

cgp_publishes_total = Counter(
    "extract_worker_cgp_publishes_total",
    "CGP packets published to NATS",
    ["subject", "status"],
)


def _build_cgp_packet(
    chunks: List[Dict[str, Any]], collection: str, request_id: str
) -> Dict[str, Any]:
    """Build a CGP v1.0 packet from ingested chunks."""
    points = []
    for i, chunk in enumerate(chunks[:50]):
        text = chunk.get("text", "")
        points.append({
            "id": f"chunk:{chunk.get('chunk_id', chunk.get('id', i))}",
            "modality": "text",
            "proj": round(min(len(text) / 500.0, 1.0), 3),
            "conf": 0.9,
            "summary": text[:200],
        })

    volume = min(len(chunks) / 100.0, 1.0)
    success = 1.0
    richness = min(
        sum(len(c.get("text", "")) for c in chunks) / 10000.0, 1.0
    )
    spectrum = [round(v, 3) for v in (volume, success, richness)]

    return {
        "spec": CGP_SPEC_VERSION,
        "summary": f"extract-worker: indexed {len(chunks)} chunks into {collection}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "super_nodes": [{
            "id": f"extract:{request_id}",
            "label": "extract-worker",
            "x": 0.0, "y": 0.0, "r": 0.3,
            "constellations": [{
                "id": f"extract.ingest.{request_id}",
                "anchor": [0.5, 0.5, 0.5],
                "spectrum": spectrum,
                "points": points,
            }],
        }],
        "meta": {
            "source": CGP_SUBJECT,
            "tags": ["extract", "indexing", "qdrant", "meilisearch"],
            "collection": collection,
            "chunk_count": len(chunks),
        },
    }


def _publish_nats_fire_and_forget(subject: str, payload: Dict[str, Any]) -> None:
    """Publish to NATS in a daemon thread (sync endpoint can't await)."""

    async def _do_publish():
        try:
            import nats as nats_pkg

            nc = await nats_pkg.connect(NATS_URL)
            await nc.publish(subject, json.dumps(payload).encode("utf-8"))
            await nc.flush()
            await nc.close()
            cgp_publishes_total.labels(subject=subject, status="ok").inc()
            logger.info("Published CGP to %s", subject)
        except Exception as exc:
            cgp_publishes_total.labels(subject=subject, status="error").inc()
            logger.warning("NATS publish to %s failed (non-fatal): %s", subject, exc)

    t = threading.Thread(target=lambda: asyncio.run(_do_publish()), daemon=True)
    t.start()
# ── end CHIT ──────────────────────────────────────────────────────────────────

app = FastAPI(title="PMOVES Extract Worker", version="1.0.0")

_embedder = None
TENSORZERO_BASE = os.environ.get("TENSORZERO_BASE_URL", "http://tensorzero-gateway:3000")
TENSORZERO_API_KEY = os.environ.get("TENSORZERO_API_KEY")
TENSORZERO_EMBED_MODEL = os.environ.get(
    "TENSORZERO_EMBED_MODEL", "tensorzero::embedding_model_name::qwen3_embedding_4b_local"
)
TENSORZERO_EMBED_BATCH_SIZE = int(os.environ.get("TENSORZERO_EMBED_BATCH_SIZE", "16"))
TENSORZERO_EMBED_TIMEOUT_SECS = float(os.environ.get("TENSORZERO_EMBED_TIMEOUT_SECS", "120"))

def _meili(method: str, path: str, **kwargs):
    headers = kwargs.pop('headers', {})
    if MEILI_API_KEY:
        headers['Authorization'] = f'Bearer {MEILI_API_KEY}'
    headers.setdefault('content-type','application/json')
    return requests.request(method, f"{MEILI_URL}{path}", headers=headers, timeout=30, **kwargs)

def _ensure_qdrant(client: QdrantClient, dim: int):
    try:
        info = client.get_collection(COLL)
    except Exception:
        client.recreate_collection(COLL, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
        return

    # Validate dimension compatibility (avoid opaque 400s later).
    try:
        params = getattr(getattr(info, "config", None), "params", None)
        if isinstance(params, dict):
            vectors = params.get("vectors") or {}
            current_dim = vectors.get("size")
        else:
            vectors = getattr(params, "vectors", None)
            current_dim = getattr(vectors, "size", None)
    except Exception:
        current_dim = None

    if current_dim and int(current_dim) != int(dim):
        allow_recreate = os.environ.get("QDRANT_RECREATE_ON_DIM_MISMATCH", "false").lower() in ("1", "true", "yes")
        if allow_recreate:
            client.recreate_collection(COLL, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
            return
        raise HTTPException(
            status_code=500,
            detail=(
                f"Qdrant collection '{COLL}' has dim={current_dim}, but embeddings are dim={dim}. "
                "Recreate the collection (data loss) or set QDRANT_COLLECTION to a new name. "
                "For dev-only auto-recreate, set QDRANT_RECREATE_ON_DIM_MISMATCH=true."
            ),
        )

def _embed(texts: List[str]):
    if EMBEDDING_BACKEND == "tensorzero":
        return _embed_tensorzero(texts)
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(MODEL)
    return _embedder.encode(texts, normalize_embeddings=True)


def _embed_tensorzero(texts: List[str]):
    url = f"{TENSORZERO_BASE.rstrip('/')}/openai/v1/embeddings"
    headers = {"content-type": "application/json"}
    if TENSORZERO_API_KEY:
        headers["Authorization"] = f"Bearer {TENSORZERO_API_KEY}"

    batch_size = max(1, TENSORZERO_EMBED_BATCH_SIZE)
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        payload = {"model": TENSORZERO_EMBED_MODEL, "input": batch}
        resp = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=TENSORZERO_EMBED_TIMEOUT_SECS,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if len(data) != len(batch):
            raise HTTPException(status_code=502, detail="TensorZero embedding response size mismatch")
        out.extend([entry.get("embedding", []) for entry in data])
    return np.array(out, dtype=float)

@app.get("/healthz")
def healthz():
    http_requests_total.labels(method='GET', endpoint='/healthz', status='200').inc()
    return {"ok": True}

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/ingest")
def ingest(body: Dict[str, Any] = Body(...)):
    """Ingest text chunks for embedding and indexing to Qdrant + Meilisearch."""
    with http_request_duration.time():
        status = "200"
        try:
            chunks = body.get('chunks') or []
            errors = body.get('errors') or []

            # Upsert chunks to Qdrant + Meili
            if chunks:
                texts = [c.get('text','') for c in chunks]
                vecs = _embed(texts)
                embeddings_processed_total.inc(len(texts))

                qc = QdrantClient(url=QDRANT_URL, timeout=30.0)
                _ensure_qdrant(qc, vecs.shape[1])
                points: List[PointStruct] = []
                for i, v in enumerate(vecs):
                    chunk = chunks[i]
                    chunk_id = chunk.get("chunk_id") or chunk.get("id") or f"chunk-{i+1}"
                    # Qdrant point IDs must be uint64 or UUID; arbitrary strings are rejected.
                    if isinstance(chunk_id, int):
                        point_id = chunk_id
                    else:
                        ns = (chunk.get("namespace") or "pmoves").strip()
                        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ns}:{chunk_id}"))
                    points.append(PointStruct(id=point_id, vector=v.tolist(), payload=chunk))

                qc.upsert(collection_name=COLL, points=points)
                qdrant_operations_total.labels(operation='upsert').inc()

                try:
                    _meili('post','/indexes', json={'uid': COLL, 'primaryKey':'chunk_id'})
                    qdrant_operations_total.labels(operation='meili_index_create').inc()
                except Exception:
                    pass
                try:
                    _meili('post', f'/indexes/{COLL}/documents', data=json.dumps(chunks))
                    qdrant_operations_total.labels(operation='meili_docs_add').inc()
                except Exception:
                    pass

                # Publish CGP packet to GEOMETRY BUS
                if CGP_PUBLISH_ENABLED:
                    try:
                        req_id = str(uuid.uuid4())
                        cgp = _build_cgp_packet(chunks, COLL, req_id)
                        _publish_nats_fire_and_forget(CGP_SUBJECT, cgp)
                        _publish_nats_fire_and_forget(SKILL_HOOK_SUBJECT, {
                            "service": "extract-worker",
                            "request_id": req_id,
                            "chunk_count": len(chunks),
                            "collection": COLL,
                            "ts": datetime.now(timezone.utc).isoformat(),
                        })
                    except Exception as cgp_exc:
                        logger.warning("CGP build/publish failed (non-fatal): %s", cgp_exc)

            # Insert errors to Supabase
            inserted = 0
            for e in errors:
                try:
                    r = requests.post(f"{SUPA}/it_errors", headers={'content-type':'application/json'}, data=json.dumps(e), timeout=20)
                    r.raise_for_status(); inserted += 1
                    qdrant_operations_total.labels(operation='supabase_error_insert').inc()
                except Exception:
                    continue

            http_requests_total.labels(method='POST', endpoint='/ingest', status=status).inc()
            return {"ok": True, "chunks": len(chunks), "errors_inserted": inserted}

        except HTTPException as e:
            status = str(e.status_code)
            http_requests_total.labels(method='POST', endpoint='/ingest', status=status).inc()
            raise
        except Exception:
            status = "500"
            http_requests_total.labels(method='POST', endpoint='/ingest', status=status).inc()
            raise
