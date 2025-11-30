import os, sys, csv
from pathlib import Path
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import requests, json as pyjson

_repo_root = Path(__file__).resolve().parents[4]
if str(_repo_root) not in sys.path:
    sys.path.append(str(_repo_root))

from libs.providers.embedding import embed_text as embed_via_providers

QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
COLL = os.environ.get("QDRANT_COLLECTION", "pmoves_chunks")
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

def load_csv(path: str, namespace: str|None=None) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            txt = row.get('text') or row.get('content')
            if not txt: continue
            doc_id = row.get('doc_id') or 'doc'
            sec = row.get('section_id') or row.get('section') or 'sec'
            chunk_id = row.get('chunk_id') or f"{doc_id}-{sec}-{i}"
            ns = namespace or row.get('namespace') or DEFAULT_NAMESPACE
            doc = {
                'doc_id': doc_id,
                'section_id': sec,
                'chunk_id': chunk_id,
                'namespace': ns,
                'text': txt,
            }
            for key in (
                'persona_id',
                'persona_slug',
                'persona_label',
                'persona_name',
                'persona_summary',
                'persona_namespace',
            ):
                val = row.get(key)
                if val:
                    doc[key] = val
            docs.append(doc)
    return docs

def main():
    if len(sys.argv) < 2:
        print('Usage: load_csv.py /path/file.csv [namespace]')
        sys.exit(2)
    path = sys.argv[1]
    ns = sys.argv[2] if len(sys.argv) > 2 else None
    docs = load_csv(path, ns)
    if not docs:
        print('No rows parsed.'); sys.exit(1)
    vectors: List[List[float]] = []
    for doc in docs:
        vec = embed_via_providers(doc['text'])
        if vec is None:
            raise RuntimeError(f"Embedding failed for chunk {doc['chunk_id']}")
        if hasattr(vec, 'tolist'):
            vec = vec.tolist()
        vectors.append([float(v) for v in vec])
    if not vectors or not vectors[0]:
        raise RuntimeError('Embedding backend returned empty vectors')
    client = QdrantClient(url=QDRANT_URL, timeout=60.0)
    ensure_qdrant_collection(client, len(vectors[0]))
    points = [PointStruct(id=i+1, vector=vec, payload=doc) for i,(doc,vec) in enumerate(zip(docs, vectors))]
    client.upsert(collection_name=COLL, points=points)
    print(f"Upserted {len(points)} points into {COLL}")
    try:
        meili_request('get', f'/indexes/{COLL}')
        meili_request('post', '/indexes', data=pyjson.dumps({'uid': COLL, 'primaryKey': 'chunk_id'}))
    except Exception:
        pass
    try:
        meili_request('post', f'/indexes/{COLL}/documents', data=pyjson.dumps(docs))
        print('Indexed documents into Meilisearch')
    except Exception:
        print('Meilisearch indexing skipped or failed')

if __name__ == '__main__':
    main()

