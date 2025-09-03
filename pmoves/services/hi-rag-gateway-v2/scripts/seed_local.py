import os, json, time
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import requests

QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
COLL = os.environ.get("QDRANT_COLLECTION", "pmoves_chunks")
MODEL = os.environ.get("SENTENCE_MODEL", "all-MiniLM-L6-v2")
MEILI_URL = os.environ.get("MEILI_URL", "http://meilisearch:7700")
MEILI_API_KEY = os.environ.get("MEILI_API_KEY", "")
NAMESPACE = os.environ.get("INDEXER_NAMESPACE", "pmoves")

def seed_docs() -> List[Dict[str, Any]]:
    texts = [
        ("pmoves_intro", "intro-1", "PMOVES is a modular orchestration mesh for AI services, built with FastAPI and Docker Compose."),
        ("pmoves_intro", "intro-2", "It integrates retrieval systems like Qdrant and Meilisearch, and supports Supabase for content workflows."),
        ("pmoves_intro", "intro-3", "The Hi-RAG Gateway provides hybrid search with optional reranking and Neo4j entity boosts."),
    ]
    out = []
    for i, (doc, sec, txt) in enumerate(texts, start=1):
        out.append({
            "doc_id": doc,
            "section_id": sec,
            "chunk_id": f"{doc}-{sec}",
            "namespace": NAMESPACE,
            "text": txt,
        })
    return out

def ensure_qdrant_collection(client: QdrantClient, dim: int):
    try:
        info = client.get_collection(COLL)
        # If exists, assume OK
        return
    except Exception:
        pass
    client.recreate_collection(
        collection_name=COLL,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
    )

def seed_qdrant(docs: List[Dict[str, Any]]):
    embedder = SentenceTransformer(MODEL)
    vecs = embedder.encode([d["text"] for d in docs], normalize_embeddings=True)

    client = QdrantClient(url=QDRANT_URL, timeout=30.0)
    ensure_qdrant_collection(client, vecs.shape[1])
    points = []
    for i, (d, v) in enumerate(zip(docs, vecs), start=1):
        points.append(PointStruct(id=i, vector=v.tolist(), payload=d))
    client.upsert(collection_name=COLL, points=points)
    return len(points)

def meili_request(method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    if MEILI_API_KEY:
        headers["Authorization"] = f"Bearer {MEILI_API_KEY}"
    headers.setdefault("content-type", "application/json")
    url = f"{MEILI_URL}{path}"
    return requests.request(method, url, headers=headers, timeout=15, **kwargs)

def seed_meili(docs: List[Dict[str, Any]]):
    try:
        r = meili_request("get", f"/indexes/{COLL}")
        if r.status_code == 404:
            meili_request("post", "/indexes", data=json.dumps({"uid": COLL, "primaryKey": "chunk_id"}))
        # add documents
        r = meili_request("post", f"/indexes/{COLL}/documents", data=json.dumps(docs))
        return True
    except Exception:
        return False

def main():
    docs = seed_docs()
    print(f"Seeding {len(docs)} docs into Qdrant collection '{COLL}' and Meili index '{COLL}' (namespace='{NAMESPACE}')...")
    n = seed_qdrant(docs)
    print(f"Qdrant upserted: {n}")
    ok = seed_meili(docs)
    print(f"Meili indexed: {ok}")
    print("Done.")

if __name__ == "__main__":
    main()

