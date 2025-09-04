import os, json
from typing import Dict, Any, List
from fastapi import FastAPI, Body, HTTPException
import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

QDRANT_URL = os.environ.get("QDRANT_URL","http://qdrant:6333")
COLL = os.environ.get("QDRANT_COLLECTION","pmoves_chunks")
MODEL = os.environ.get("SENTENCE_MODEL","all-MiniLM-L6-v2")
MEILI_URL = os.environ.get("MEILI_URL","http://meilisearch:7700")
MEILI_API_KEY = os.environ.get("MEILI_API_KEY","")
SUPA = os.environ.get("SUPA_REST_URL","http://postgrest:3000")

app = FastAPI(title="PMOVES Extract Worker", version="1.0.0")

_embedder = None

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
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(MODEL)
    return _embedder.encode(texts, normalize_embeddings=True)

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

