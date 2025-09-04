
import os, time, math, json
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Body
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, SearchRequest
from sentence_transformers import SentenceTransformer
from FlagEmbedding import FlagReranker
import requests

QDRANT_URL = os.environ.get("QDRANT_URL","http://qdrant:6333")
COLL = os.environ.get("QDRANT_COLLECTION","pmoves_chunks")
MODEL = os.environ.get("SENTENCE_MODEL","all-MiniLM-L6-v2")
RERANK_ENABLE = os.environ.get("RERANK_ENABLE","true").lower()=="true"
RERANK_MODEL = os.environ.get("RERANK_MODEL","BAAI/bge-reranker-base")
RERANK_TOPN = int(os.environ.get("RERANK_TOPN","50"))
RERANK_K = int(os.environ.get("RERANK_K","10"))
NAMESPACE_DEFAULT = os.environ.get("INDEXER_NAMESPACE","pmoves")

qdrant = QdrantClient(url=QDRANT_URL, timeout=30.0)
embedder = SentenceTransformer(MODEL)
reranker = None
if RERANK_ENABLE:
    try:
        reranker = FlagReranker(RERANK_MODEL, use_fp16=True)
    except Exception as e:
        print("Reranker init failed:", e)
        reranker = None

class QueryReq(BaseModel):
    query: str
    namespace: str = Field(default=NAMESPACE_DEFAULT)
    k: int = 10
    alpha: float = 0.7
    use_rerank: Optional[bool] = None
    rerank_topn: Optional[int] = None
    rerank_k: Optional[int] = None

class QueryHit(BaseModel):
    chunk_id: str
    text: str
    score: float
    rerank_score: Optional[float] = None
    payload: Dict[str, Any] = {}

class QueryResp(BaseModel):
    query: str
    k: int
    used_rerank: bool
    hits: List[QueryHit]

app = FastAPI(title="PMOVES Hi-RAG Gateway v2 (with rerank)", version="2.0.0")

@app.get("/hirag/admin/stats")
def stats():
    return {
        "rerank_enabled": RERANK_ENABLE,
        "rerank_model": RERANK_MODEL if RERANK_ENABLE else None,
        "rerank_loaded": reranker is not None
    }

@app.post("/hirag/query", response_model=QueryResp)
def hirag_query(req: QueryReq = Body(...)):
    vec = embedder.encode(req.query, normalize_embeddings=True).tolist()

    # base vector search
    must = [FieldCondition(key="namespace", match=MatchValue(value=req.namespace))]
    sr = SearchRequest(
        vector=vec, limit=max(req.k, RERANK_TOPN),
        filter=Filter(must=must),
        with_payload=True, with_vectors=False
    )
    hits = qdrant.search(collection_name=COLL, search_request=sr)

    # map to simple structure
    base = [{
        "chunk_id": h.payload.get("chunk_id") or h.id,
        "text": h.payload.get("text",""),
        "score": float(h.score),
        "payload": h.payload
    } for h in hits]

    # optional rerank
    enable = req.use_rerank if req.use_rerank is not None else RERANK_ENABLE
    topn = req.rerank_topn or RERANK_TOPN
    outk = req.rerank_k or req.k or RERANK_K

    used = False
    if enable and reranker is not None and base:
        pool = base[:topn]
        pairs = [[req.query, p["text"]] for p in pool]
        scores = reranker.compute_score(pairs, normalize=True)
        for p, s in zip(pool, scores):
            p["rerank_score"] = float(s)
            # simple fusion: multiply (can switch to weighted sum)
            p["score"] = float(p["score"] * (0.5 + 0.5*s))
        pool.sort(key=lambda x: x["score"], reverse=True)
        base = pool[:outk]
        used = True
    else:
        base = base[:req.k]

    return {
        "query": req.query,
        "k": len(base),
        "used_rerank": used,
        "hits": base
    }
