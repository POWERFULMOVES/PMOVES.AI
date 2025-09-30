
import os, time, math, json, logging, re, sys, contextlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Body, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from FlagEmbedding import FlagReranker
from rapidfuzz import fuzz
from neo4j import GraphDatabase
import requests
import asyncio
import nats
import psycopg

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
NEO4J_URL = (os.environ.get("NEO4J_URL","bolt://neo4j:7687") or "").strip()
NEO4J_USER = os.environ.get("NEO4J_USER","neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD","neo4j")
NEO4J_DICT_REFRESH_SEC = int(os.environ.get("NEO4J_DICT_REFRESH_SEC","60"))
NEO4J_DICT_LIMIT = int(os.environ.get("NEO4J_DICT_LIMIT","50000"))
ENTITY_CACHE_TTL = int(os.environ.get("ENTITY_CACHE_TTL","60"))
ENTITY_CACHE_MAX = int(os.environ.get("ENTITY_CACHE_MAX","1000"))

SUPABASE_REST_URL = os.environ.get("SUPA_REST_URL") or os.environ.get("SUPABASE_REST_URL")
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
)
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_REALTIME_URL = os.environ.get("SUPABASE_REALTIME_URL") or os.environ.get("REALTIME_URL")
SUPABASE_REALTIME_KEY = (
    SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY or os.environ.get("REALTIME_ANON_KEY")
)
GEOMETRY_CACHE_WARM_LIMIT = int(os.environ.get("GEOMETRY_CACHE_WARM_LIMIT", "64"))
GEOMETRY_REALTIME_BACKOFF = float(os.environ.get("GEOMETRY_REALTIME_BACKOFF", "5.0"))

TAILSCALE_ONLY = os.environ.get("TAILSCALE_ONLY","false").lower()=="true"
TAILSCALE_ADMIN_ONLY = os.environ.get("TAILSCALE_ADMIN_ONLY","false").lower()=="true"
TAILSCALE_CIDRS = [c.strip() for c in os.environ.get("TAILSCALE_CIDRS","100.64.0.0/10").split(",") if c.strip()]

HTTP_PORT = int(os.environ.get("HIRAG_HTTP_PORT","8086"))
NAMESPACE_DEFAULT = os.environ.get("INDEXER_NAMESPACE","pmoves")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hirag.gateway.v2")

qdrant = QdrantClient(url=QDRANT_URL, timeout=30.0)

# Lazy/optional Neo4j: allow running without the neo4j service
driver = None
if NEO4J_URL:
    try:
        driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))
    except Exception:
        logging.getLogger("hirag.gateway.v2").warning("Neo4j unavailable at %s; graph features disabled", NEO4J_URL)
        driver = None

_embedder = None

def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(MODEL)
    return _embedder

# --- In-memory rooms for WebSocket signaling and geometry broadcast ---
_rooms: Dict[str, List[WebSocket]] = {}
_room_ws_id: Dict[str, Dict[WebSocket, str]] = {}
_room_ids: Dict[str, List[str]] = {}

def _room_get(name: str) -> List[WebSocket]:
    return _rooms.setdefault(name, [])

async def _room_add(name: str, ws: WebSocket):
    _room_get(name).append(ws)
    _room_ws_id.setdefault(name, {})[ws] = ""
    _room_ids.setdefault(name, [])

def _room_remove(name: str, ws: WebSocket):
    lst = _rooms.get(name, [])
    if ws in lst:
        lst.remove(ws)
    if name in _room_ws_id and ws in _room_ws_id[name]:
        pid = _room_ws_id[name].pop(ws, "")
        if pid and name in _room_ids and pid in _room_ids[name]:
            try:
                _room_ids[name].remove(pid)
            except ValueError:
                pass

async def _room_broadcast(name: str, msg: Dict[str, Any], skip: WebSocket | None = None):
    dead = []
    for ws in list(_rooms.get(name, [])):
        if skip is not None and ws is skip:
            continue
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for d in dead:
        _room_remove(name, d)

async def _room_broadcast_roster(name: str):
    peers = _room_ids.get(name, [])
    await _room_broadcast(name, {"type":"roster", "room": name, "peers": peers})

def embed_query(text: str):
    # Try provider chain first; fall back to local SentenceTransformer
    try:
        vec = _embed_via_providers(text)
        # Ensure vector is a 1-D list/tuple
        if hasattr(vec, 'tolist'):
            vec = vec.tolist()
        return vec
    except Exception:
        logger.info("Provider embedding failed; falling back to %s", MODEL)
        try:
            emb = _get_embedder().encode([text], normalize_embeddings=True)
            return emb[0].tolist() if hasattr(emb, 'tolist') else emb[0]
        except Exception as e:
            logger.exception("Embedding fallback failed")
            raise HTTPException(500, f"Embedding error: {e}")

def ensure_qdrant_collection(vector_dim: int):
    try:
        qdrant.get_collection(COLL)
        return
    except Exception:
        pass
    try:
        qdrant.recreate_collection(
            collection_name=COLL,
            vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE)
        )
        logger.info("(re)created Qdrant collection %s [dim=%d, metric=cosine]", COLL, vector_dim)
    except Exception as e:
        logger.exception("ensure_qdrant_collection failed")
        raise HTTPException(500, f"Qdrant collection error: {e}")

def hybrid_score(vec_score: float, lex_score: float, alpha: float=ALPHA) -> float:
    return alpha*vec_score + (1.0-alpha)*lex_score

_warm_entities: Dict[str, set] = {}
_warm_last = 0.0

def refresh_warm_dictionary():
    global _warm_entities, _warm_last
    if driver is None:
        _warm_entities = {}
        _warm_last = time.time()
        return
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
if driver is not None:
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

# ensure repo root on sys.path for importing shared tools
try:
    _repo_root = Path(__file__).resolve().parents[2]
    if str(_repo_root) not in sys.path:
        sys.path.append(str(_repo_root))
except Exception:
    pass

# Geometry Bus: ShapeStore and CHIT flags
try:
    from services.common.shape_store import ShapeStore
    shape_store = ShapeStore(capacity=10_000)
    logging.getLogger("hirag.gateway.v2").info("ShapeStore initialized (v2)")
except Exception as _e:
    logging.getLogger("hirag.gateway.v2").exception("ShapeStore init failed: %s", _e)
    shape_store = None

_geometry_realtime_task: Optional[asyncio.Task] = None


def _derive_realtime_url() -> Optional[str]:
    if SUPABASE_REALTIME_URL:
        return SUPABASE_REALTIME_URL
    if not SUPABASE_REST_URL:
        return None
    rest = SUPABASE_REST_URL.rstrip("/")
    if "postgrest" in rest or rest.endswith(":3000"):
        return "ws://realtime:4000/socket/websocket"
    base = rest
    if base.endswith("/rest/v1"):
        base = base[: -len("/rest/v1")]
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    return base.rstrip("/") + "/realtime/v1"


async def _warm_shapes_from_supabase() -> None:
    if shape_store is None or not SUPABASE_REST_URL:
        if shape_store is not None:
            logger.info("ShapeStore warm skipped; SUPA_REST_URL not configured")
        return
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    try:
        count = await shape_store.warm_from_db(
            rest_url=SUPABASE_REST_URL,
            service_key=key,
            limit=GEOMETRY_CACHE_WARM_LIMIT,
        )
        logger.info("ShapeStore warmed with %d Supabase constellations", count)
    except Exception:
        logger.exception("ShapeStore warm_from_db failed")


async def _phoenix_heartbeat(ws, interval: float = 25.0) -> None:
    ref = 1
    try:
        while True:
            msg = {"topic": "phoenix", "event": "heartbeat", "payload": {}, "ref": str(ref)}
            await ws.send(json.dumps(msg))
            ref += 1
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("Supabase heartbeat error")


async def _geometry_realtime_worker(ws_url: str, api_key: str) -> None:
    try:
        import websockets
    except ImportError:
        logger.warning("websockets not installed; skipping Supabase realtime subscription")
        return

    while True:
        full_url = ws_url
        if "apikey=" not in full_url:
            sep = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{sep}apikey={api_key}&vsn=2.0.0"
        try:
            async with websockets.connect(full_url, ping_interval=20, ping_timeout=20, max_queue=None) as ws:
                join_payload = {
                    "topic": "realtime:geometry.cgp.v1",
                    "event": "phx_join",
                    "payload": {"config": {"broadcast": {"ack": False, "self": True}}},
                    "ref": "1",
                }
                await ws.send(json.dumps(join_payload))
                logger.info("Subscribed to Supabase realtime geometry.cgp.v1 channel")
                heartbeat = asyncio.create_task(_phoenix_heartbeat(ws))
                try:
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except Exception:
                            continue
                        if msg.get("topic") != "realtime:geometry.cgp.v1":
                            continue
                        payload = msg.get("payload") or {}
                        event_payload: Optional[Dict[str, Any]] = None
                        if isinstance(payload, dict):
                            if payload.get("type") == "geometry.cgp.v1" and isinstance(payload.get("data"), dict):
                                event_payload = payload
                            elif payload.get("type") == "geometry.cgp.v1" and isinstance(payload.get("payload"), dict):
                                event_payload = {"type": "geometry.cgp.v1", "data": payload.get("payload")}
                            else:
                                evt = payload.get("event") or payload.get("type")
                                data = (
                                    payload.get("data")
                                    or payload.get("payload")
                                    or payload.get("record")
                                    or payload.get("new")
                                )
                                if evt == "geometry.cgp.v1" and isinstance(data, dict):
                                    event_payload = {"type": "geometry.cgp.v1", "data": data}
                        if event_payload:
                            try:
                                shape_store.on_geometry_event(event_payload)
                            except Exception:
                                logger.exception("Failed to apply Supabase geometry event")
                finally:
                    heartbeat.cancel()
                    with contextlib.suppress(Exception):
                        await heartbeat
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception(
                "Supabase realtime listener error; retrying in %.1fs", max(1.0, GEOMETRY_REALTIME_BACKOFF)
            )
            await asyncio.sleep(max(1.0, GEOMETRY_REALTIME_BACKOFF))


@app.on_event("startup")
async def _on_startup() -> None:
    if shape_store is None:
        logger.info("ShapeStore unavailable; geometry cache warm skipped")
        return
    await _warm_shapes_from_supabase()
    global _geometry_realtime_task
    if _geometry_realtime_task is None:
        ws_url = _derive_realtime_url()
        api_key = SUPABASE_REALTIME_KEY
        if ws_url and api_key:
            _geometry_realtime_task = asyncio.create_task(_geometry_realtime_worker(ws_url, api_key))
            logger.info("Supabase realtime geometry listener started (url=%s)", ws_url)
        else:
            logger.info("Supabase realtime subscription skipped; missing URL or API key")


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    global _geometry_realtime_task
    if _geometry_realtime_task is not None:
        _geometry_realtime_task.cancel()
        with contextlib.suppress(Exception):
            await _geometry_realtime_task
        _geometry_realtime_task = None

CHIT_REQUIRE_SIGNATURE = os.environ.get("CHIT_REQUIRE_SIGNATURE", "false").lower()=="true"
CHIT_PASSPHRASE = os.environ.get("CHIT_PASSPHRASE", "")
CHIT_DECRYPT_ANCHORS = os.environ.get("CHIT_DECRYPT_ANCHORS", "false").lower()=="true"
CHIT_DECODE_TEXT = os.environ.get("CHIT_DECODE_TEXT", "false").lower()=="true"
CHIT_DECODE_IMAGE = os.environ.get("CHIT_DECODE_IMAGE", "false").lower()=="true"
CHIT_DECODE_AUDIO = os.environ.get("CHIT_DECODE_AUDIO", "false").lower()=="true"
CHIT_CODEBOOK_PATH = os.environ.get("CHIT_CODEBOOK_PATH", "datasets/structured_dataset.jsonl")
CHIT_T5_MODEL = os.environ.get("CHIT_T5_MODEL","t5-small")
CHIT_CLIP_MODEL = os.environ.get("CHIT_CLIP_MODEL","clip-ViT-B-32")
CHIT_PERSIST_DB = os.environ.get("CHIT_PERSIST_DB","false").lower()=="true"

PGHOST = os.environ.get("PGHOST")
PGPORT = int(os.environ.get("PGPORT","5432"))
PGUSER = os.environ.get("PGUSER")
PGPASSWORD = os.environ.get("PGPASSWORD")
PGDATABASE = os.environ.get("PGDATABASE")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

_codebook_cache = None
_codebook_mtime = None

def _load_codebook(path: str):
    global _codebook_cache, _codebook_mtime
    try:
        st = os.stat(path)
        if _codebook_cache is not None and _codebook_mtime == st.st_mtime:
            return _codebook_cache
        items = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line=line.strip()
                if not line: continue
                try:
                    items.append(json.loads(line))
                except Exception:
                    continue
        _codebook_cache = items
        _codebook_mtime = st.st_mtime
        return items
    except FileNotFoundError:
        return []
    except Exception:
        logger.exception("codebook load error")
        return []

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

def _tailscale_required(admin_only: bool) -> bool:
    if TAILSCALE_ONLY:
        return True
    if admin_only:
        return TAILSCALE_ADMIN_ONLY
    return False


def _tailscale_violation_detail(admin_only: bool) -> str:
    return (
        "Admin endpoints restricted to Tailscale network"
        if admin_only
        else "Service restricted to Tailscale network"
    )


def _tailscale_ip_allowed(ip: str, admin_only: bool) -> bool:
    if not _tailscale_required(admin_only):
        return True
    return _ip_in_cidrs(ip, TAILSCALE_CIDRS)


def require_tailscale(request: Request, admin_only: bool = False):
    if not _tailscale_required(admin_only):
        return
    ip = _client_ip(request)
    if not _tailscale_ip_allowed(ip, admin_only):
        raise HTTPException(status_code=403, detail=_tailscale_violation_detail(admin_only))


def require_admin_tailscale(request: Request):
    return require_tailscale(request, admin_only=True)

@app.get("/hirag/admin/stats")
def stats(_=Depends(require_admin_tailscale)):
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
def hirag_query(req: QueryReq = Body(...), _=Depends(require_tailscale)):
    try:
        vec = embed_query(req.query)
        # Lazily ensure collection exists with cosine + correct dim
        try:
            dim = len(vec)
            ensure_qdrant_collection(dim)
        except Exception:
            pass
        must = [FieldCondition(key="namespace", match=MatchValue(value=req.namespace))]
        hits = qdrant.search(
            collection_name=COLL,
            query_vector=vec,
            limit=max(req.k, RERANK_TOPN),
            query_filter=Filter(must=must),
            with_payload=True,
        )
    except Exception as e:
        logger.exception("Qdrant search error")
        raise HTTPException(503, f"Qdrant search error: {e}")

    # lexical scores
    meili_scores = meili_lexical(req.query, req.namespace, req.k) if USE_MEILI else {}
    gterms = set([t.lower() for t in graph_terms(req.query, entity_types=req.entity_types)]) if driver is not None and GRAPH_BOOST > 0 else set()

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
def hirag_admin_refresh(_=Depends(require_admin_tailscale)):
    refresh_warm_dictionary()
    return {"ok": True, "last_refresh": _warm_last}

@app.post("/hirag/admin/cache/clear")
def hirag_admin_cache_clear(_=Depends(require_admin_tailscale)):
    # no explicit cache; warm dictionary reload covers
    refresh_warm_dictionary()
    return {"ok": True}

@app.get("/")
def index(_=Depends(require_tailscale)):
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


# ---------------- Geometry Bus endpoints (v2) ----------------
from fastapi import UploadFile
import io

@app.post("/geometry/event")
def geometry_event(body: Dict[str, Any], _=Depends(require_tailscale)):
    if shape_store is None:
        raise HTTPException(503, "ShapeStore unavailable")
    payload = body.get("data") if isinstance(body, dict) else None
    if not isinstance(payload, dict):
        raise HTTPException(400, "missing data")
    if CHIT_REQUIRE_SIGNATURE:
        try:
            from tools.chit_security import verify_cgp, decrypt_anchors
        except Exception:
            raise HTTPException(500, "security module not available")
        if not CHIT_PASSPHRASE:
            raise HTTPException(500, "CHIT_REQUIRE_SIGNATURE=true but CHIT_PASSPHRASE not set")
        if not verify_cgp(payload, CHIT_PASSPHRASE):
            raise HTTPException(401, "invalid CGP signature")
        if CHIT_DECRYPT_ANCHORS:
            payload = decrypt_anchors(payload, CHIT_PASSPHRASE)
    shape_store.on_geometry_event({"type":"geometry.cgp.v1","data":payload})
    # optional persistence to Postgres for Supabase Realtime
    if CHIT_PERSIST_DB and PGHOST and PGUSER and PGPASSWORD and PGDATABASE:
        try:
            _persist_cgp_to_db(payload)
        except Exception:
            logger.exception("persist CGP failed")
    # notify websocket geometry channel (best-effort)
    try:
        import anyio
        async def _notify():
            await _room_broadcast("geometry", {"type":"geometry.cgp.v1","data": payload})
        anyio.from_thread.run(_notify)
    except Exception:
        pass
    return {"ok": True}

@app.get("/shape/point/{point_id}/jump")
def shape_point_jump(point_id: str, _=Depends(require_tailscale)):
    if shape_store is None:
        raise HTTPException(503, "ShapeStore unavailable")
    loc = shape_store.jump_locator(point_id)
    if not loc:
        raise HTTPException(404, f"point '{point_id}' not found")
    return {"ok": True, "locator": loc}

@app.post("/geometry/decode/text")
def geometry_decode_text(body: Dict[str, Any], _=Depends(require_tailscale)):
    if not CHIT_DECODE_TEXT:
        raise HTTPException(501, "text decoder disabled")
    mode = (body.get("mode") or "geometry").lower()
    const_id = body.get("constellation_id")
    k = int(body.get("k", 5))
    const = shape_store.get_constellation(const_id) if (shape_store and const_id) else None
    if mode == "learned":
        try:
            from transformers import pipeline  # type: ignore
        except Exception:
            raise HTTPException(500, "transformers not installed")
        texts = []
        cb = _load_codebook(CHIT_CODEBOOK_PATH)
        for rec in cb[: min(64, len(cb))]:
            t = rec.get("text") or rec.get("summary")
            if t: texts.append(t)
        if const:
            s = const.get("summary");
            if s: texts.insert(0, s)
        if not texts:
            raise HTTPException(400, "no codebook or constellation text available")
        nlp = pipeline("summarization", model=CHIT_T5_MODEL)
        out = nlp("\n".join(texts)[:4000], max_length=128, min_length=32, do_sample=False)
        return {"mode": mode, "summary": out[0].get("summary_text",""), "used": len(texts)}
    else:
        pts = []
        if const:
            for p in const.get("points", []) or []:
                cid = p.get("id");
                if not cid: continue
                pts.append({
                    "id": cid,
                    "text": p.get("text"),
                    "proj": p.get("proj"),
                    "conf": p.get("conf")
                })
        pts.sort(key=lambda x: (x.get("conf") or 0.0, x.get("proj") or 0.0), reverse=True)
        return {"mode": mode, "points": pts[:k]}

@app.post("/geometry/calibration/report")
def geometry_calibration_report(body: Dict[str, Any], _=Depends(require_tailscale)):
    def _js(p, q):
        import math
        def _kl(a, b):
            eps = 1e-9
            s = 0.0
            for i in range(min(len(a), len(b))):
                ai = max(a[i], eps); bi = max(b[i], eps)
                s += ai * math.log(ai/bi)
            return s
        m = [(pi+qi)*0.5 for pi,qi in zip(p,q)]
        return 0.5*(_kl(p,m)+_kl(q,m))
    def _w1(p, q):
        from itertools import accumulate
        cdp=list(accumulate(p)); cdq=list(accumulate(q))
        n=max(1,len(cdp));
        return sum(abs((cdp[i] if i<len(cdp) else 1.0)-(cdq[i] if i<len(cdq) else 1.0)) for i in range(n))/n
    data = body.get("data")
    const_ids = body.get("constellation_ids") or []
    consts = []
    if isinstance(data, dict):
        for sn in data.get("super_nodes", []) or []:
            consts.extend(sn.get("constellations", []) or [])
    for cid in const_ids:
        c = shape_store.get_constellation(cid) if shape_store else None
        if c: consts.append(c)
    report=[]
    for c in consts:
        s = c.get("spectrum") or []
        if not s:
            report.append({"id": c.get("id"), "coverage": 0.0, "js": None, "w1": None}); continue
        s=[float(x) for x in s]; mass=sum(s) or 1.0; s=[x/mass for x in s]
        u=[1.0/len(s)]*len(s)
        js=_js(s,u); w1=_w1(s,u); coverage=sum(1 for x in s if x>0.01)/float(len(s))
        report.append({"id": c.get("id"), "coverage": coverage, "js": js, "w1": w1})
    return {"constellations": report}

@app.post("/geometry/decode/image")
def geometry_decode_image(body: Dict[str, Any], _=Depends(require_tailscale)):
    if not CHIT_DECODE_IMAGE:
        raise HTTPException(501, "image decoder disabled")
    try:
        from sentence_transformers import SentenceTransformer
        from PIL import Image
        import numpy as np
    except Exception:
        raise HTTPException(500, "missing dependencies for image decode (sentence-transformers, Pillow)")
    const_id = body.get("constellation_id")
    images = body.get("images") or []
    if not images:
        raise HTTPException(400, "images list required")
    const = shape_store.get_constellation(const_id) if (shape_store and const_id) else None
    text = body.get("text") or (const.get("summary") if const else None)
    if not text:
        raise HTTPException(400, "text or constellation summary required for anchor")
    try:
        model = SentenceTransformer(CHIT_CLIP_MODEL)
        text_emb = model.encode([text], normalize_embeddings=True, convert_to_numpy=True)
        img_list=[]
        for url in images:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert('RGB')
            img_list.append(img)
        img_embs = model.encode(img_list, normalize_embeddings=True, convert_to_numpy=True)
        sims = (img_embs @ text_emb.T).squeeze()  # cosine if normalized
        ranked = sorted(zip(images, sims.tolist()), key=lambda x: x[1], reverse=True)
        return {"ranked": [{"url": u, "score": float(s)} for u,s in ranked]}
    except Exception as e:
        logger.exception("image decode error")
        raise HTTPException(500, f"image decode error: {e}")

@app.post("/geometry/decode/audio")
def geometry_decode_audio(body: Dict[str, Any], _=Depends(require_tailscale)):
    if not CHIT_DECODE_AUDIO:
        raise HTTPException(501, "audio decoder disabled")
    try:
        from laion_clap import CLAP_Module  # type: ignore
    except Exception:
        raise HTTPException(500, "missing laion-clap/torch; install extras and set CHIT_DECODE_AUDIO=true")
    const_id = body.get("constellation_id")
    audios = body.get("audios") or []
    if not audios:
        raise HTTPException(400, "audios list required")
    const = shape_store.get_constellation(const_id) if (shape_store and const_id) else None
    text = body.get("text") or (const.get("summary") if const else None)
    if not text:
        raise HTTPException(400, "text or constellation summary required for anchor")
    try:
        model = CLAP_Module(enable_fusion=True)
        # Will download default ckpt if not provided; can be heavy
        model.load_ckpt()
        a_emb = model.get_audio_embedding_from_filelist(x=audios, use_tensor=False)
        t_emb = model.get_text_embedding([text], use_tensor=False)
        # cosine similarity when normalized
        import numpy as np
        a = np.asarray(a_emb, dtype=float)
        t = np.asarray(t_emb, dtype=float).reshape(1,-1)
        # normalize
        a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
        t = t / (np.linalg.norm(t, axis=1, keepdims=True) + 1e-9)
        sims = (a @ t.T).squeeze()
        ranked = sorted(zip(audios, sims.tolist()), key=lambda x: x[1], reverse=True)
        return {"ranked": [{"path": u, "score": float(s)} for u,s in ranked]}
    except Exception as e:
        logger.exception("audio decode error")
        raise HTTPException(500, f"audio decode error: {e}")


def _persist_cgp_to_db(cgp: Dict[str, Any]):
    """Persist anchors, constellations, and points to Postgres.
    This is a best-effort dev helper for Supabase Realtime; RLS must allow service inserts.
    """
    conn = psycopg.connect(host=PGHOST, port=PGPORT, user=PGUSER, password=PGPASSWORD, dbname=PGDATABASE, autocommit=False)
    try:
        with conn.cursor() as cur:
            for sn in cgp.get("super_nodes", []) or []:
                for const in sn.get("constellations", []) or []:
                    anchor = const.get("anchor")
                    anchor_enc = const.get("anchor_enc")
                    dim = (len(anchor) if isinstance(anchor, (list, tuple)) else (0))
                    # insert anchor
                    cur.execute(
                        """
                        INSERT INTO public.anchors(kind, dim, anchor, anchor_enc, meta)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            'multi', int(dim) if dim else 0,
                            anchor if isinstance(anchor, list) else None,
                            json.dumps(anchor_enc) if anchor_enc else None,
                            json.dumps({})
                        )
                    )
                    anchor_id = cur.fetchone()[0]
                    spectrum = const.get("spectrum") if isinstance(const.get("spectrum"), list) else None
                    radial = const.get("radial_minmax") if isinstance(const.get("radial_minmax"), list) else [None, None]
                    summary = const.get("summary")
                    # insert constellation
                    cur.execute(
                        """
                        INSERT INTO public.constellations(anchor_id, summary, radial_min, radial_max, spectrum, meta)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (anchor_id, summary, radial[0] if radial else None, radial[1] if radial else None, spectrum, json.dumps({}))
                    )
                    constellation_id = cur.fetchone()[0]
                    # insert points
                    pts = const.get("points", []) or []
                    for p in pts:
                        modality = p.get("modality") or p.get("mod") or 'text'
                        ref_id = p.get("ref_id") or p.get("video_id") or p.get("doc_id") or ''
                        cur.execute(
                            """
                            INSERT INTO public.shape_points(
                              constellation_id, modality, ref_id, t_start, t_end, frame_idx, token_start, token_end, proj, conf, meta)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """,
                            (
                              constellation_id, modality, ref_id,
                              p.get("t_start"), p.get("t_end"), p.get("frame_idx"),
                              p.get("token_start"), p.get("token_end"),
                              p.get("proj"), p.get("conf"), json.dumps({k:v for k,v in p.items() if k not in {
                                'id','modality','mod','ref_id','video_id','doc_id','t_start','t_end','frame_idx','token_start','token_end','proj','conf','text'
                              }})
                            )
                        )
        conn.commit()
    finally:
        conn.close()

# ---------------- Static UI and WebSockets ----------------
app.mount("/geometry", StaticFiles(directory=str(Path(__file__).resolve().parent / "web"), html=True), name="geometry")

@app.websocket("/ws/signaling/{room}")
async def ws_signaling(ws: WebSocket, room: str):
    ip = ws.client.host if ws.client else "127.0.0.1"
    if not _tailscale_ip_allowed(ip, admin_only=False):
        logger.warning("Rejecting websocket connection from non-Tailnet IP %s", ip)
        await ws.close(code=1008, reason=_tailscale_violation_detail(admin_only=False))
        return
    await ws.accept()
    await _room_add(room, ws)
    try:
        while True:
            data = await ws.receive_json()
            # Handle presence to maintain a server-side roster
            if isinstance(data, dict) and data.get("type") == "presence":
                pid = str(data.get("from") or "")
                _room_ws_id.setdefault(room, {})[ws] = pid
                ids = _room_ids.setdefault(room, [])
                if pid and pid not in ids:
                    ids.append(pid)
                await _room_broadcast_roster(room)
                continue
            # broadcast to room peers (simple relay)
            await _room_broadcast(room, {"room": room, "relay": data}, skip=ws)
    except WebSocketDisconnect:
        _room_remove(room, ws)
        await _room_broadcast_roster(room)
    except Exception:
        _room_remove(room, ws)
        try:
            await ws.close()
        except Exception:
            pass
        try:
            await _room_broadcast_roster(room)
        except Exception:
            pass


@app.post("/mesh/handshake")
def mesh_handshake(body: Dict[str, Any], _=Depends(require_admin_tailscale)):
    """Publish a shape-capsule to NATS mesh subject (mesh.shape.handshake.v1).
    Body: { capsule: {...} }
    """
    capsule = body.get("capsule")
    if not isinstance(capsule, dict):
        raise HTTPException(400, "capsule required")
    payload = {"type": "shape-capsule", "capsule": capsule}
    try:
        async def _pub():
            nc = await nats.connect(servers=[NATS_URL])
            await nc.publish("mesh.shape.handshake.v1", json.dumps(payload).encode())
            await nc.flush(); await nc.drain()
        asyncio.run(_pub())
        return {"ok": True}
    except Exception as e:
        logger.exception("mesh publish failed")
        raise HTTPException(500, f"mesh publish failed: {e}")


@app.post("/geometry/import_db")
def import_db(body: Dict[str, Any], _=Depends(require_admin_tailscale)):
    """Persist a CGP directly into Postgres (forces persistence), update ShapeStore, and broadcast.
    Accepts either { data: <CGP> } or { capsule: { kind:'cgp', data: <CGP> } }.
    """
    payload = body.get("data")
    if not isinstance(payload, dict):
        cap = body.get("capsule") or {}
        if isinstance(cap, dict) and isinstance(cap.get("data"), dict):
            payload = cap.get("data")
    if not isinstance(payload, dict):
        raise HTTPException(400, "missing CGP data")
    # echo into store and WS
    shape_store.on_geometry_event({"type":"geometry.cgp.v1","data": payload})
    try:
        _persist_cgp_to_db(payload)
    except Exception:
        logger.exception("import_db persist failed")
        raise HTTPException(500, "persist failed (check DB creds / RLS)")
    # notify UI
    try:
        import anyio
        async def _notify():
            await _room_broadcast("geometry", {"type":"geometry.cgp.v1","data": payload})
        anyio.from_thread.run(_notify)
    except Exception:
        pass
    return {"ok": True}


# ---------------- Batch upsert for JSONL/JSON chunks ----------------
class UpsertItem(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    namespace: str = Field(default=NAMESPACE_DEFAULT)
    section_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

class UpsertReq(BaseModel):
    items: Optional[List[UpsertItem]] = None
    jsonl: Optional[str] = None  # newline-separated JSON
    ensure_collection: bool = True
    index_lexical: bool = False

@app.post("/hirag/upsert-batch")
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
        except Exception:
            pass

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
        points.append(PointStruct(id=cid, vector=vec, payload=payload))

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
            headers = {"Content-Type":"application/json"}
            if MEILI_API_KEY:
                headers["Authorization"] = f"Bearer {MEILI_API_KEY}"
            # Ensure index exists (ignore if it does)
            requests.post(f"{MEILI_URL}/indexes", headers=headers, data=json.dumps({"uid": COLL} ), timeout=5)
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
