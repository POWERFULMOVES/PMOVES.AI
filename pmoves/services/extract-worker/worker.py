import os, json
import uuid
from typing import Dict, Any, List
from fastapi import FastAPI, Body, HTTPException
import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import numpy as np

QDRANT_URL = os.environ.get("QDRANT_URL","http://qdrant:6333")
COLL = os.environ.get("QDRANT_COLLECTION","pmoves_chunks_qwen3")
MODEL = os.environ.get("SENTENCE_MODEL","all-MiniLM-L6-v2")
MEILI_URL = os.environ.get("MEILI_URL","http://meilisearch:7700")
MEILI_API_KEY = os.environ.get("MEILI_API_KEY","")
SUPA = os.environ.get("SUPA_REST_URL","http://postgrest:3000")
EMBEDDING_BACKEND = os.environ.get("EMBEDDING_BACKEND", "sentence-transformers").lower()

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
    return {"ok": True}

@app.post("/ingest")
def ingest(body: Dict[str, Any] = Body(...)):
    chunks = body.get('chunks') or []
    errors = body.get('errors') or []
    # Upsert chunks to Qdrant + Meili
    if chunks:
        texts = [c.get('text','') for c in chunks]
        vecs = _embed(texts)
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
        try:
            _meili('post','/indexes', json={'uid': COLL, 'primaryKey':'chunk_id'})
        except Exception:
            pass
        try:
            _meili('post', f'/indexes/{COLL}/documents', data=json.dumps(chunks))
        except Exception:
            pass
    # Insert errors to Supabase
    inserted = 0
    for e in errors:
        try:
            r = requests.post(f"{SUPA}/it_errors", headers={'content-type':'application/json'}, data=json.dumps(e), timeout=20)
            r.raise_for_status(); inserted += 1
        except Exception:
            continue
    return {"ok": True, "chunks": len(chunks), "errors_inserted": inserted}
