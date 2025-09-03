import os, sys, json
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
DEFAULT_NAMESPACE = os.environ.get("INDEXER_NAMESPACE", "pmoves")

def ensure_qdrant_collection(client: QdrantClient, dim: int):
    try:
        client.get_collection(COLL)
        return
    except Exception:
        pass
    client.recreate_collection(
        collection_name=COLL,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
    )

def meili_request(method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    if MEILI_API_KEY:
        headers["Authorization"] = f"Bearer {MEILI_API_KEY}"
    headers.setdefault("content-type", "application/json")
    url = f"{MEILI_URL}{path}"
    return requests.request(method, url, headers=headers, timeout=60, **kwargs)

def load_jsonl(path: str, namespace_override: str|None=None) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            obj = json.loads(line)
            txt = obj.get('text') or obj.get('content')
            if not txt: continue
            doc_id = obj.get('doc_id') or obj.get('document_id') or 'doc'
            sec = obj.get('section_id') or obj.get('section') or 'sec'
            chunk_id = obj.get('chunk_id') or f"{doc_id}-{sec}-{len(docs)+1}"
            ns = namespace_override or obj.get('namespace') or DEFAULT_NAMESPACE
            docs.append({
                'doc_id': doc_id,
                'section_id': sec,
                'chunk_id': chunk_id,
                'namespace': ns,
                'text': txt,
            })
    return docs

def main():
    if len(sys.argv) < 2:
        print('Usage: load_jsonl.py /path/file.jsonl [namespace]')
        sys.exit(2)
    path = sys.argv[1]
    ns = sys.argv[2] if len(sys.argv) > 2 else None
    docs = load_jsonl(path, ns)
    if not docs:
        print('No documents parsed.'); sys.exit(1)
    embedder = SentenceTransformer(MODEL)
    vecs = embedder.encode([d['text'] for d in docs], normalize_embeddings=True)
    client = QdrantClient(url=QDRANT_URL, timeout=60.0)
    ensure_qdrant_collection(client, vecs.shape[1])
    points = [PointStruct(id=i+1, vector=v.tolist(), payload=d) for i,(d,v) in enumerate(zip(docs, vecs))]
    client.upsert(collection_name=COLL, points=points)
    print(f"Upserted {len(points)} points into {COLL}")
    try:
        meili_request('get', f'/indexes/{COLL}')
        meili_request('post', '/indexes', data=json.dumps({'uid': COLL, 'primaryKey': 'chunk_id'}))
    except Exception:
        pass
    try:
        meili_request('post', f'/indexes/{COLL}/documents', data=json.dumps(docs))
        print('Indexed documents into Meilisearch')
    except Exception:
        print('Meilisearch indexing skipped or failed')

if __name__ == '__main__':
    main()

