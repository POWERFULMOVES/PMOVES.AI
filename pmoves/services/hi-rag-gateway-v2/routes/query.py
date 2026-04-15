"""Query and upsert endpoints for hi-rag-gateway-v2."""

import json
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Request, Depends
try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None  # type: ignore
try:
    from qdrant_client.http.models import Filter, FieldCondition, MatchValue, PointStruct
except ImportError:
    Filter = None  # type: ignore
    FieldCondition = None  # type: ignore
    MatchValue = None  # type: ignore
    PointStruct = None  # type: ignore

from config import (
    RERANK_ENABLE, RERANK_PROVIDER, RERANK_TOPN, RERANK_K, RERANK_FUSION,
    USE_MEILI, GRAPH_BOOST, COLL, MEILI_URL, MEILI_API_KEY, NAMESPACE_DEFAULT, logger, _reranker,
)
from models import QueryReq, QueryResp, UpsertReq
from embeddings import embed_query
from rerank import hybrid_score, _tensorzero_rerank, _get_reranker
from security import require_tailscale, require_admin_tailscale, _client_ip
from clients.qdrant import qdrant, _qdrant_search, ensure_qdrant_collection
from clients.neo4j import driver, graph_terms
from clients.openai_compat import meili_lexical, _extract_persona

router = APIRouter()


@router.post("/hirag/query", response_model=QueryResp)
def hirag_query(req: QueryReq = Body(...), request: Request = None, _=Depends(require_tailscale)):
    client_ip = None
    try:
        client_ip = _client_ip(request) if request is not None else None
    except Exception:
        client_ip = None
    logger.warning("hirag.query incoming namespace=%s ip=%s", getattr(req, "namespace", None), client_ip)
    try:
        vec = embed_query(req.query)
        try:
            dim = len(vec)
            ensure_qdrant_collection(dim)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("ensure_qdrant_collection non-fatal: %s", e)
        ns = req.namespace
        if ns and ns != "*":
            must = [FieldCondition(key="namespace", match=MatchValue(value=ns))]
            qf = Filter(must=must)
        else:
            qf = None
        hits = _qdrant_search(
            collection_name=COLL,
            query_vector=vec,
            limit=max(req.k, RERANK_TOPN),
            query_filter=qf,
            with_payload=True,
            with_vectors=False,
        )
        logger.warning("hirag.query hits=%d namespace=%s ip=%s", len(hits), req.namespace, client_ip)
    except Exception as e:
        logger.exception("Qdrant search error")
        raise HTTPException(503, f"Qdrant search error: {e}")

    # lexical scores
    meili_scores = meili_lexical(req.query, req.namespace, req.k) if USE_MEILI else {}
    gterms = set([t.lower() for t in graph_terms(req.query, entity_types=req.entity_types)]) if driver is not None and GRAPH_BOOST > 0 else set()

    base = []
    for h in hits:
        payload = h.payload or {}
        txt = payload.get("text", "")
        cid = payload.get("chunk_id") or h.id
        lex = float(meili_scores.get(cid, 0.0)) if USE_MEILI else (fuzz.token_set_ratio(req.query, txt)/100.0)
        vecs = float(h.score)
        g_hit = any(term in txt.lower() for term in gterms) if gterms else False
        score = hybrid_score(vecs, lex, req.alpha) + (GRAPH_BOOST if g_hit else 0.0)
        persona = _extract_persona(payload)
        base.append({
            "chunk_id": cid,
            "text": txt,
            "score": score,
            "graph_match": bool(g_hit),
            "payload": payload,
            "persona": persona,
        })

    # optional rerank
    enable = req.use_rerank if req.use_rerank is not None else RERANK_ENABLE
    topn = req.rerank_topn or RERANK_TOPN
    outk = req.rerank_k or req.k or RERANK_K

    used = False
    rerank_provider: Optional[str] = None
    if enable and base:
        pool = sorted(base, key=lambda x: x["score"], reverse=True)[:topn]
        scores: Optional[List[float]] = None
        if pool and RERANK_PROVIDER in {"tensorzero", "tz", "tzero"}:
            scores = _tensorzero_rerank(req.query, pool)
            if scores is not None:
                rerank_provider = "tensorzero"
        if scores is None and pool:
            try:
                rr = _get_reranker()
            except Exception:
                rr = None
            if rr is not None:
                pairs = [[req.query, p["text"]] for p in pool]
                try:
                    scores = rr.compute_score(pairs, normalize=True)
                except Exception as e:
                    if isinstance(e, ValueError) and "batch" in str(e).lower():
                        scores = []
                        for pair in pairs:
                            try:
                                res = rr.compute_score([pair], normalize=True)
                                if isinstance(res, (list, tuple)):
                                    scores.extend(float(r) for r in res)
                                else:
                                    scores.append(float(res))
                            except Exception:
                                logger.exception("Reranker single compute failed")
                                scores.append(0.0)
                    else:
                        logger.exception("Reranker compute failed")
                        scores = [0.0] * len(pool)
                if scores is not None and rerank_provider is None:
                    fallback_label = RERANK_PROVIDER
                    if fallback_label in {"tensorzero", "tz", "tzero"}:
                        fallback_label = "flag"
                    rerank_provider = fallback_label
        if scores is not None:
            if len(scores) != len(pool):
                scores = (scores + [0.0] * len(pool))[:len(pool)]
            fused = []
            for p, s in zip(pool, scores):
                p = dict(p)
                p["rerank_score"] = float(s)
                if RERANK_FUSION == "wsum":
                    p["score"] = float(0.5 * p["score"] + 0.5 * s)
                else:
                    p["score"] = float(p["score"] * (0.5 + 0.5 * s))
                fused.append(p)
            base = sorted(fused, key=lambda x: x["score"], reverse=True)[:outk]
            used = True
    if not used:
        base = sorted(base, key=lambda x: x["score"], reverse=True)[:req.k]

    return {
        "query": req.query,
        "k": len(base),
        "used_rerank": used,
        "rerank_provider": rerank_provider,
        "hits": base,
    }


@router.post("/hirag/upsert-batch")
def hirag_upsert_batch(req: UpsertReq = Body(...), _=Depends(require_admin_tailscale)):
    # Parse items from jsonl if provided
    items: List[Dict[str, Any]] = []
    if req.items:
        items = [i.model_dump() for i in req.items]
    elif req.jsonl:
        for line in req.jsonl.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    else:
        raise HTTPException(400, "Either items or jsonl must be provided")

    if not items:
        return {"ok": True, "upserted": 0}

    vectors = []
    for it in items:
        txt = it.get("text", "")
        vectors.append(embed_query(txt))

    if req.ensure_collection and vectors:
        try:
            ensure_qdrant_collection(len(vectors[0]))
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("ensure_qdrant_collection non-fatal: %s", e)

    points = []
    for it, vec in zip(items, vectors):
        cid = it.get("chunk_id") or it.get("id")
        if not cid:
            continue
        payload = {
            "doc_id": it.get("doc_id"),
            "section_id": it.get("section_id"),
            "chunk_id": cid,
            "text": it.get("text"),
            "namespace": it.get("namespace", NAMESPACE_DEFAULT)
        }
        extra = it.get("payload") or {}
        if isinstance(extra, dict):
            for k, v in extra.items():
                payload.setdefault(k, v)
        qdrant_id = str(uuid.uuid5(uuid.NAMESPACE_URL, cid))
        points.append(PointStruct(id=qdrant_id, vector=vec, payload=payload))

    try:
        if points:
            qdrant.upsert(collection_name=COLL, points=points)
    except Exception as e:
        logger.exception("Qdrant upsert failed")
        raise HTTPException(503, f"Qdrant upsert error: {e}")

    # Optional lexical indexing (MeiliSearch)
    indexed = 0
    if (req.index_lexical or USE_MEILI) and items:
        try:
            import requests
            headers = {"Content-Type": "application/json"}
            if MEILI_API_KEY:
                headers["Authorization"] = f"Bearer {MEILI_API_KEY}"
            requests.post(f"{MEILI_URL}/indexes", headers=headers, data=json.dumps({"uid": COLL}), timeout=5)
            docs = []
            for it in items:
                docs.append({
                    "id": it.get("chunk_id") or it.get("id"),
                    "chunk_id": it.get("chunk_id") or it.get("id"),
                    "doc_id": it.get("doc_id"),
                    "section_id": it.get("section_id"),
                    "text": it.get("text"),
                    "namespace": it.get("namespace", NAMESPACE_DEFAULT)
                })
            if docs:
                r = requests.post(f"{MEILI_URL}/indexes/{COLL}/documents", headers=headers, data=json.dumps(docs), timeout=30)
                if r.ok:
                    indexed = len(docs)
        except Exception:
            logger.exception("Meili indexing failed")

    return {"ok": True, "upserted": len(points), "lexical_indexed": indexed}
