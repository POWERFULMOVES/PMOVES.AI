
import os, time, math, json, logging, re
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Body, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, SearchRequest
from sentence_transformers import SentenceTransformer
from FlagEmbedding import FlagReranker
from rapidfuzz import fuzz
from neo4j import GraphDatabase
import requests

QDRANT_URL = os.environ.get("QDRANT_URL","http://qdrant:6333")
COLL = os.environ.get("QDRANT_COLLECTION","pmoves_chunks")
MODEL = os.environ.get("SENTENCE_MODEL","all-MiniLM-L6-v2")
ALPHA = float(os.environ.get("ALPHA", "0.7"))

RERANK_ENABLE = os.environ.get("RERANK_ENABLE","true").lower()=="true"
RERANK_MODEL = os.environ.get("RERANK_MODEL","BAAI/bge-reranker-base")
RERANK_TOPN = int(os.environ.get("RERANK_TOPN","50"))
RERANK_K = int(os.environ.get("RERANK_K","10"))
RERANK_FUSION = os.environ.get("RERANK_FUSION","mul").lower()  # mul|wsum

USE_MEILI = os.environ.get("USE_MEILI","false").lower()=="true"
MEILI_URL = os.environ.get("MEILI_URL","http://meilisearch:7700")
MEILI_API_KEY = os.environ.get("MEILI_API_KEY","master_key")

from libs.providers.embedding import embed_text as _embed_via_providers

GRAPH_BOOST = float(os.environ.get("GRAPH_BOOST","0.15"))
NEO4J_URL = os.environ.get("NEO4J_URL","bolt://neo4j:7687")
NEO4J_USER = os.environ.get("NEO4J_USER","neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD","neo4j")
NEO4J_DICT_REFRESH_SEC = int(os.environ.get("NEO4J_DICT_REFRESH_SEC","60"))
NEO4J_DICT_LIMIT = int(os.environ.get("NEO4J_DICT_LIMIT","50000"))
ENTITY_CACHE_TTL = int(os.environ.get("ENTITY_CACHE_TTL","60"))
ENTITY_CACHE_MAX = int(os.environ.get("ENTITY_CACHE_MAX","1000"))

TAILSCALE_ONLY = os.environ.get("TAILSCALE_ONLY","false").lower()=="true"
TAILSCALE_CIDRS = [c.strip() for c in os.environ.get("TAILSCALE_CIDRS","100.64.0.0/10").split(",") if c.strip()]

HTTP_PORT = int(os.environ.get("HIRAG_HTTP_PORT","8086"))
NAMESPACE_DEFAULT = os.environ.get("INDEXER_NAMESPACE","pmoves")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hirag.gateway.v2")

qdrant = QdrantClient(url=QDRANT_URL, timeout=30.0)
driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))

def embed_query(text: str):
    try:
        return _embed_via_providers(text)
    except Exception as e:
        logger.exception("Embedding providers failed")
        raise HTTPException(500, f"Embedding error: {e}")

def hybrid_score(vec_score: float, lex_score: float, alpha: float=ALPHA) -> float:
    return alpha*vec_score + (1.0-alpha)*lex_score

_warm_entities: Dict[str, set] = {}
_warm_last = 0.0

def refresh_warm_dictionary():
    global _warm_entities, _warm_last
    try:
        tmp: Dict[str, set] = {}
        with driver.session() as s:
            recs = s.run("MATCH (e:Entity) RETURN e.value AS v, coalesce(e.type,'UNK') AS t LIMIT $lim",
                         lim=NEO4J_DICT_LIMIT)
            for r in recs:
                v = r["v"]; t = (r["t"] or "UNK").upper()
                if not v: continue
                tmp.setdefault(t, set()).add(v)
        _warm_entities = tmp
        _warm_last = time.time()
    except Exception:
        logger.exception("warm dictionary error")

def warm_loop():
    while True:
        try:
            refresh_warm_dictionary()
        except Exception:
            logger.exception("warm loop error")
        time.sleep(max(15, NEO4J_DICT_REFRESH_SEC))

import threading as _t
_t.Thread(target=warm_loop, daemon=True).start()

def graph_terms(query: str, limit: int = 8, entity_types: Optional[List[str]] = None):
    toks = [t.lower() for t in re.split(r"\W+", query) if t and len(t) > 2]
    if not toks: return []
    types_norm = set([x.upper() for x in (entity_types or [])]) if entity_types else None
    out = set()
    for tname, values in _warm_entities.items():
        if types_norm and tname not in types_norm:
            continue
        for val in values:
            lv = val.lower()
            if any(tok in lv for tok in toks):
                out.add(val)
                if len(out) >= limit:
                    return list(out)[:limit]
    return list(out)[:limit]

def meili_lexical(query, namespace, limit):
    if not USE_MEILI: return {}
    try:
        headers={'Authorization': f'Bearer {MEILI_API_KEY}'} if MEILI_API_KEY else {}
        payload={'q': query, 'limit': max(10, limit*3), 'filter': [f"namespace = '{namespace}'"]}
        r = requests.post(f"{MEILI_URL}/indexes/{COLL}/search", json=payload, headers=headers, timeout=10)
        if not r.ok:
            return {}
        hits = r.json().get('hits', [])
        out = {}
        for i, h in enumerate(hits):
            cid = h.get('chunk_id') or h.get('id')
            if not cid: continue
            score = h.get('_rankingScore') or (1.0 - i/max(1.0, len(hits)))
            out[cid] = float(score)
        return out
    except Exception:
        logger.exception("meili lexical error")
        return {}

class QueryReq(BaseModel):
    query: str
    namespace: str = Field(default=NAMESPACE_DEFAULT)
    k: int = 10
    alpha: float = ALPHA
    use_rerank: Optional[bool] = None
    rerank_topn: Optional[int] = None
    rerank_k: Optional[int] = None
    entity_types: Optional[List[str]] = None

class QueryHit(BaseModel):
    chunk_id: str
    text: str
    score: float
    rerank_score: Optional[float] = None
    graph_match: Optional[bool] = None
    payload: Dict[str, Any] = {}

class QueryResp(BaseModel):
    query: str
    k: int
    used_rerank: bool
    hits: List[QueryHit]

app = FastAPI(title="PMOVES Hi-RAG Gateway v2 (hybrid + rerank)", version="2.1.0")

def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

def _ip_in_cidrs(ip: str, cidrs):
    import ipaddress
    try:
        ip_obj = ipaddress.ip_address(ip)
        for c in cidrs:
            try:
                if ip_obj in ipaddress.ip_network(c):
                    return True
            except Exception:
                continue
    except Exception:
        logger.exception("_ip_in_cidrs parse error for ip %s", ip)
        return False
    return False

def require_tailscale(request: Request):
    if not TAILSCALE_ONLY:
        return
    ip = _client_ip(request)
    if not _ip_in_cidrs(ip, TAILSCALE_CIDRS):
        raise HTTPException(status_code=403, detail="Admin restricted to Tailscale network")

@app.get("/hirag/admin/stats")
def stats(_=Depends(require_tailscale)):
    return {
        "rerank_enabled": RERANK_ENABLE,
        "rerank_model": RERANK_MODEL if RERANK_ENABLE else None,
        "rerank_loaded": reranker is not None,
        "use_meili": USE_MEILI,
        "graph": {"boost": GRAPH_BOOST, "types": len(_warm_entities), "last_refresh": _warm_last},
        "alpha": ALPHA,
        "collection": COLL
    }

@app.post("/hirag/query", response_model=QueryResp)
def hirag_query(req: QueryReq = Body(...)):
    try:
        vec = embed_query(req.query)
        must = [FieldCondition(key="namespace", match=MatchValue(value=req.namespace))]
        sr = SearchRequest(
            vector=vec, limit=max(req.k, RERANK_TOPN),
            filter=Filter(must=must),
            with_payload=True, with_vectors=False
        )
        hits = qdrant.search(collection_name=COLL, search_request=sr)
    except Exception as e:
        logger.exception("Qdrant search error")
        raise HTTPException(503, f"Qdrant search error: {e}")

    # lexical scores
    meili_scores = meili_lexical(req.query, req.namespace, req.k) if USE_MEILI else {}
    gterms = set([t.lower() for t in graph_terms(req.query, entity_types=req.entity_types)])

    base = []
    for h in hits:
        txt = h.payload.get("text", "")
        cid = h.payload.get("chunk_id") or h.id
        lex = float(meili_scores.get(cid, 0.0)) if USE_MEILI else (fuzz.token_set_ratio(req.query, txt)/100.0)
        vecs = float(h.score)
        g_hit = any(term in txt.lower() for term in gterms) if gterms else False
        score = hybrid_score(vecs, lex, req.alpha) + (GRAPH_BOOST if g_hit else 0.0)
        base.append({
            "chunk_id": cid,
            "text": txt,
            "score": score,
            "graph_match": bool(g_hit),
            "payload": h.payload
        })

    # optional rerank
    enable = req.use_rerank if req.use_rerank is not None else RERANK_ENABLE
    topn = req.rerank_topn or RERANK_TOPN
    outk = req.rerank_k or req.k or RERANK_K

    used = False
    if enable and base:
        try:
            rr = _get_reranker()
        except Exception:
            rr = None
        if rr is not None:
            pool = sorted(base, key=lambda x: x["score"], reverse=True)[:topn]
            pairs = [[req.query, p["text"]] for p in pool]
            try:
                scores = rr.compute_score(pairs, normalize=True)
            except Exception as e:
                logger.exception("Reranker compute failed")
                scores = [0.0]*len(pool)
            fused = []
            for p, s in zip(pool, scores):
                p = dict(p)
                p["rerank_score"] = float(s)
                if RERANK_FUSION == "wsum":
                    # weighted sum with 0.5 vec/lex hybrid already baked into p['score']
                    p["score"] = float(0.5*p["score"] + 0.5*s)
                else:
                    # multiplicative fusion keeps ordering stable
                    p["score"] = float(p["score"] * (0.5 + 0.5*s))
                fused.append(p)
            base = sorted(fused, key=lambda x: x["score"], reverse=True)[:outk]
            used = True
    if not used:
        base = sorted(base, key=lambda x: x["score"], reverse=True)[:req.k]

    return {"query": req.query, "k": len(base), "used_rerank": used, "hits": base}

@app.post("/hirag/admin/refresh")
def hirag_admin_refresh(_=Depends(require_tailscale)):
    refresh_warm_dictionary()
    return {"ok": True, "last_refresh": _warm_last}

@app.post("/hirag/admin/cache/clear")
def hirag_admin_cache_clear(_=Depends(require_tailscale)):
    # no explicit cache; warm dictionary reload covers
    refresh_warm_dictionary()
    return {"ok": True}

@app.get("/")
def index():
    return {"ok": True, "service": "hi-rag-gateway-v2", "hint": "POST /hirag/query"}

# lazy-init reranker to reduce cold start time
_reranker = None
def _get_reranker():
    global _reranker
    if _reranker is not None:
        return _reranker
    if not RERANK_ENABLE:
        return None
    try:
        _reranker = FlagReranker(RERANK_MODEL, use_fp16=True)
        return _reranker
    except Exception as e:
        logger.exception("Reranker init failed")
        return None
