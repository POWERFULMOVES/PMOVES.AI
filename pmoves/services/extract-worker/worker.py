import os, json
from typing import Dict, Any, List
from fastapi import FastAPI, Body, HTTPException
import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import numpy as np

QDRANT_URL = os.environ.get("QDRANT_URL","http://qdrant:6333")
COLL = os.environ.get("QDRANT_COLLECTION","pmoves_chunks")
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
    "TENSORZERO_EMBED_MODEL", "tensorzero::embedding_model_name::gemma_embed_local"
)

def _meili(method: str, path: str, **kwargs):
    headers = kwargs.pop('headers', {})
    if MEILI_API_KEY:
        headers['Authorization'] = f'Bearer {MEILI_API_KEY}'
    headers.setdefault('content-type','application/json')
    return requests.request(method, f"{MEILI_URL}{path}", headers=headers, timeout=30, **kwargs)

def _ensure_qdrant(client: QdrantClient, dim: int):
    try:
        client.get_collection(COLL)
    except Exception:
        client.recreate_collection(COLL, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))

def _embed(texts: List[str]):
    if EMBEDDING_BACKEND == "tensorzero":
        return _embed_tensorzero(texts)
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(MODEL)
    return _embedder.encode(texts, normalize_embeddings=True)


def _embed_tensorzero(texts: List[str]):
    url = f"{TENSORZERO_BASE.rstrip('/')}/openai/v1/embeddings"
    payload = {"model": TENSORZERO_EMBED_MODEL, "input": texts}
    headers = {"content-type": "application/json"}
    if TENSORZERO_API_KEY:
        headers["Authorization"] = f"Bearer {TENSORZERO_API_KEY}"
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if len(data) != len(texts):
        raise HTTPException(status_code=502, detail="TensorZero embedding response size mismatch")
    return np.array([entry.get("embedding", []) for entry in data], dtype=float)

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
        points = [PointStruct(id=i+1, vector=v.tolist(), payload=chunks[i]) for i, v in enumerate(vecs)]
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
