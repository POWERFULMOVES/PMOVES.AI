import os, time, math, json, logging, re, sys, contextlib, ipaddress, copy, threading
import importlib.util
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Body, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, Distance, VectorParams, PointStruct
import uuid
from sentence_transformers import SentenceTransformer
from FlagEmbedding import FlagReranker
import torch
from rapidfuzz import fuzz
from neo4j import GraphDatabase
import requests
from urllib.parse import quote_plus
from services.common.geometry_params import get_decoder_pack
from services.common.hrm_sidecar import HrmDecoderController
import asyncio
import nats
import psycopg

QDRANT_URL = os.environ.get("QDRANT_URL","http://qdrant:6333")
COLL = os.environ.get("QDRANT_COLLECTION","pmoves_chunks")
MODEL = os.environ.get("SENTENCE_MODEL","all-MiniLM-L6-v2")
ALPHA = float(os.environ.get("ALPHA", "0.7"))

# Collect rerank validation notes so startup logs and admin routes can expose them.
_RERANK_CONFIG_ERRORS: List[str] = []
_RERANK_CONFIG_WARNINGS: List[str] = []


def _parse_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    val = str(raw).strip().lower()
    truthy = {"1", "true", "yes", "y", "on"}
    falsy = {"0", "false", "no", "n", "off"}
    if val in truthy:
        return True
    if val in falsy:
        return False
    _RERANK_CONFIG_WARNINGS.append(f"{name} value {raw!r} not recognised; using default {default}")
    return default


def _parse_positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        _RERANK_CONFIG_ERRORS.append(f"{name} must be an integer; received {raw!r}")
        return default
    if value <= 0:
        _RERANK_CONFIG_ERRORS.append(f"{name} must be positive; received {value}")
        return default
    return value


def _parse_optional_bool(name: str) -> Optional[bool]:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return None
    val = str(raw).strip().lower()
    truthy = {"1", "true", "yes", "y", "on"}
    falsy = {"0", "false", "no", "n", "off"}
    if val in truthy:
        return True
    if val in falsy:
        return False
    _RERANK_CONFIG_WARNINGS.append(
        f"{name} value {raw!r} not recognised; ignoring override"
    )
    return None


RERANK_ENABLE = _parse_bool("RERANK_ENABLE", True)
_default_rerank_model = "Qwen/Qwen3-Reranker-4B"
RERANK_MODEL = (os.environ.get("RERANK_MODEL", _default_rerank_model) or _default_rerank_model).strip()
# Optional local model snapshot path (bind-mounted inside the GPU container).
_rerank_model_path_raw = (os.environ.get("RERANK_MODEL_PATH") or "").strip()
if _rerank_model_path_raw:
    _rerank_model_path = Path(_rerank_model_path_raw)
    if _rerank_model_path.exists():
        RERANK_MODEL_PATH = str(_rerank_model_path)
    else:
        RERANK_MODEL_PATH = None
        _RERANK_CONFIG_ERRORS.append(
            f"RERANK_MODEL_PATH {_rerank_model_path_raw!r} not found; falling back to hub id"
        )
else:
    RERANK_MODEL_PATH = None
RERANK_MODEL_RESOLVED = RERANK_MODEL_PATH or RERANK_MODEL
# Optional label override for reporting (does not force reload)
_rerank_model_label = os.environ.get("RERANK_MODEL_LABEL")
RERANK_TOPN = _parse_positive_int("RERANK_TOPN", 50)
RERANK_K = _parse_positive_int("RERANK_K", 10)
RERANK_FUSION = (os.environ.get("RERANK_FUSION", "mul") or "mul").strip().lower()  # mul|wsum
if RERANK_FUSION not in {"mul", "wsum"}:
    _RERANK_CONFIG_WARNINGS.append(f"RERANK_FUSION {RERANK_FUSION!r} not recognised; using 'mul'")
    RERANK_FUSION = "mul"
_provider_raw = (os.environ.get("RERANK_PROVIDER", "flag") or "flag").strip().lower()
_allowed_providers = {"flag", "tensorzero", "tz", "tzero"}
if _provider_raw not in _allowed_providers:
    _RERANK_CONFIG_WARNINGS.append(f"RERANK_PROVIDER {_provider_raw!r} not recognised; using 'flag'")
    RERANK_PROVIDER = "flag"
else:
    RERANK_PROVIDER = _provider_raw

if RERANK_K > RERANK_TOPN:
    _RERANK_CONFIG_WARNINGS.append(
        f"RERANK_K {RERANK_K} exceeds RERANK_TOPN {RERANK_TOPN}; truncating to topn"
    )
    RERANK_K = RERANK_TOPN

RERANK_USE_FP16_OVERRIDE = _parse_optional_bool("RERANK_USE_FP16")

# lazy-init reranker to reduce cold start time; declared early for diagnostics
_reranker = None


def get_rerank_status() -> Dict[str, Any]:
    return {
        "enabled": RERANK_ENABLE,
        "model": RERANK_MODEL,
        "model_resolved": RERANK_MODEL_RESOLVED,
        "model_label": _rerank_model_label,
        "model_path": RERANK_MODEL_PATH,
        "provider": RERANK_PROVIDER,
        "topn": RERANK_TOPN,
        "k": RERANK_K,
        "fusion": RERANK_FUSION,
        "device": "cuda" if DEVICE == "cuda" else "cpu",
        "cuda_available": _CUDA_AVAILABLE,
        "use_fp16_requested": RERANK_USE_FP16_OVERRIDE,
        "use_fp16_effective": _RERANK_FP16_EFFECTIVE,
        "loaded": bool(_reranker),
        "errors": list(_RERANK_CONFIG_ERRORS),
        "warnings": list(_RERANK_CONFIG_WARNINGS),
    }

TENSORZERO_BASE_URL = (os.environ.get("TENSORZERO_BASE_URL") or "").strip()
TENSORZERO_RERANK_FUNCTION = (os.environ.get("TENSORZERO_RERANK_FUNCTION", "hi_rag_rerank") or "hi_rag_rerank").strip()
TENSORZERO_RERANK_TIMEOUT = float(os.environ.get("TENSORZERO_RERANK_TIMEOUT", "20"))
TENSORZERO_API_KEY = (os.environ.get("TENSORZERO_API_KEY") or "").strip()

USE_MEILI = os.environ.get("USE_MEILI","false").lower()=="true"
MEILI_URL = os.environ.get("MEILI_URL","http://meilisearch:7700")
MEILI_API_KEY = os.environ.get("MEILI_API_KEY","master_key")

_USE_CUDA_ENV = os.environ.get("USE_CUDA", "true").lower() == "true"
_CUDA_AVAILABLE = torch.cuda.is_available()
DEVICE = "cuda" if _USE_CUDA_ENV and _CUDA_AVAILABLE else "cpu"
_RERANK_FP16_EFFECTIVE = (
    RERANK_USE_FP16_OVERRIDE if RERANK_USE_FP16_OVERRIDE is not None else DEVICE == "cuda"
)

_RERANK_STATUS_CACHE = get_rerank_status()

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
# Optional internal REST base explicitly pointing at host-gateway; prefer for derivations
SUPABASE_REST_INTERNAL_URL = os.environ.get("SUPA_REST_INTERNAL_URL") or None
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
)
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_REALTIME_URL = (
    os.environ.get("SUPABASE_REALTIME_URL")
    or os.environ.get("REALTIME_URL")
    or ""
).strip()
SUPABASE_REALTIME_DISABLED = SUPABASE_REALTIME_URL.lower() in {"", "disabled", "none"}
if SUPABASE_REALTIME_DISABLED:
    SUPABASE_REALTIME_URL = ""
# For backend realtime subscriptions, we need a JWT (not sb_secret_ format)
# Supabase CLI uses sb_secret_ format in SUPABASE_SERVICE_ROLE_KEY, but realtime needs JWT
# SUPABASE_SERVICE_KEY (without _ROLE) typically contains the JWT format
_jwt_service_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
_explicit_realtime_key = os.environ.get("SUPABASE_REALTIME_KEY") or os.environ.get("REALTIME_ANON_KEY")
# For realtime: prefer JWT keys, avoid sb_secret_ format which doesn't work with websockets
def _is_jwt(key: str) -> bool:
    return key and key.startswith("eyJ") and key.count(".") == 2
SUPABASE_REALTIME_KEY = (
    _jwt_service_key if _is_jwt(_jwt_service_key) else
    _explicit_realtime_key if _is_jwt(_explicit_realtime_key) else
    SUPABASE_ANON_KEY if _is_jwt(SUPABASE_ANON_KEY) else
    _jwt_service_key or _explicit_realtime_key or SUPABASE_ANON_KEY
)
GEOMETRY_CACHE_WARM_LIMIT = int(os.environ.get("GEOMETRY_CACHE_WARM_LIMIT", "64"))
# Realtime connection retry configuration
GEOMETRY_REALTIME_BACKOFF = float(os.environ.get("GEOMETRY_REALTIME_BACKOFF", "5.0"))  # Initial retry delay (seconds)
GEOMETRY_REALTIME_MAX_BACKOFF = float(os.environ.get("GEOMETRY_REALTIME_MAX_BACKOFF", "60.0"))  # Max retry delay cap (seconds)
GEOMETRY_REALTIME_STARTUP_GRACE = float(os.environ.get("GEOMETRY_REALTIME_STARTUP_GRACE", "120.0"))  # Use WARNING (not ERROR) for this duration

TAILSCALE_ONLY = os.environ.get("TAILSCALE_ONLY","false").lower()=="true"
TAILSCALE_ADMIN_ONLY = os.environ.get("TAILSCALE_ADMIN_ONLY","false").lower()=="true"
TAILSCALE_CIDRS = [c.strip() for c in os.environ.get("TAILSCALE_CIDRS","100.64.0.0/10").split(",") if c.strip()]
TRUSTED_PROXY_SOURCES = [c.strip() for c in os.environ.get("HIRAG_TRUSTED_PROXIES", "").split(",") if c.strip()]

HTTP_PORT = int(os.environ.get("HIRAG_HTTP_PORT","8086"))
NAMESPACE_DEFAULT = os.environ.get("INDEXER_NAMESPACE","pmoves")

logging.basicConfig(level=logging.INFO)
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger("hirag.gateway.v2")

if RERANK_ENABLE:
    logger.info(
        "Rerank enabled with model=%s provider=%s topn=%s k=%s fusion=%s device=%s",
        _rerank_model_label or RERANK_MODEL,
        _RERANK_STATUS_CACHE["provider"],
        _RERANK_STATUS_CACHE["topn"],
        _RERANK_STATUS_CACHE["k"],
        _RERANK_STATUS_CACHE["fusion"],
        _RERANK_STATUS_CACHE["device"],
    )
else:
    logger.info(
        "Rerank disabled (model=%s provider=%s device=%s)",
        _rerank_model_label or RERANK_MODEL,
        _RERANK_STATUS_CACHE["provider"],
        _RERANK_STATUS_CACHE["device"],
    )

for _warn in _RERANK_STATUS_CACHE["warnings"]:
    logger.warning("Rerank config warning: %s", _warn)

for _err in _RERANK_STATUS_CACHE["errors"]:
    logger.error("Rerank config error: %s", _err)

if DEVICE == "cuda":
    logger.info("CUDA detected; embeddings and reranker will run on GPU")
elif _USE_CUDA_ENV and not _CUDA_AVAILABLE:
    logger.warning("USE_CUDA requested but torch reports no CUDA device; falling back to CPU")
else:
    logger.info("Running in CPU mode")

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
        _embedder = SentenceTransformer(MODEL, device=DEVICE)
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
    # Try provider chain first; fall back to local SentenceTransformer when unavailable
    vec = None
    try:
        vec = _embed_via_providers(text)
    except Exception:
        logger.exception("Provider embedding failed; will attempt fallback")
        vec = None

    vec = _coerce_vector(vec)
    if vec:
        return vec

    logger.info("Embedding providers unavailable; falling back to %s", MODEL)
    try:
        emb = _get_embedder().encode([text], normalize_embeddings=True)
        if hasattr(emb, "tolist"):
            emb = emb.tolist()
        candidate = emb[0] if isinstance(emb, list) and emb else None
        candidate = _coerce_vector(candidate)
        if not candidate:
            raise RuntimeError("sentence-transformers returned empty vector")
        return candidate
    except Exception as e:
        logger.exception("Embedding fallback failed")
        raise HTTPException(500, f"Embedding error: {e}")


def _coerce_vector(vec: Any) -> Optional[List[float]]:
    if vec is None:
        return None
    if hasattr(vec, "tolist"):
        try:
            vec = vec.tolist()
        except Exception:
            return None
    if not isinstance(vec, (list, tuple)):
        return None
    out: List[float] = []
    try:
        for item in vec:
            out.append(float(item))
    except (TypeError, ValueError):
        return None
    return out if out else None

def ensure_qdrant_collection(vector_dim: int):
    """Create or resync the Qdrant collection when the embed dimension changes."""
    try:
        info = qdrant.get_collection(COLL)
    except Exception:
        info = None

    needs_recreate = False
    if info is not None:
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
        if current_dim is None:
            logger.info("Qdrant collection %s dimension unknown; recreating", COLL)
            needs_recreate = True
        elif current_dim != vector_dim:
            logger.info(
                "Qdrant collection %s dimension changed (%s → %s); recreating",
                COLL,
                current_dim,
                vector_dim,
            )
            needs_recreate = True
        elif info is not None and not needs_recreate:
            return

    try:
        if info is None or needs_recreate:
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
            # Avoid Neo4j "UnknownLabelWarning" when the graph hasn't been seeded yet.
            count_result = s.run(
                "MATCH (e) WHERE 'Entity' IN labels(e) RETURN count(e) AS cnt"
            ).single()
            if not count_result or not count_result["cnt"]:
                _warm_entities = {}
                _warm_last = time.time()
                return
            recs = s.run(
                (
                    "MATCH (e) WHERE 'Entity' IN labels(e) "
                    "WITH e, CASE WHEN 'type' IN keys(e) THEN e.type ELSE 'UNK' END AS typ "
                    "RETURN e.value AS v, typ AS t "
                    "LIMIT $lim"
                ),
                lim=NEO4J_DICT_LIMIT,
            )
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


def _extract_persona(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    keys = (
        "persona_id",
        "persona_slug",
        "persona_label",
        "persona_name",
        "persona_summary",
        "persona_namespace",
    )
    persona = {k: payload.get(k) for k in keys if payload.get(k)}
    return persona or None

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
    persona: Optional[Dict[str, Any]] = None

class QueryResp(BaseModel):
    query: str
    k: int
    used_rerank: bool
    rerank_provider: Optional[str] = None
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
    from services.common import geometry_params
    shape_store = ShapeStore(capacity=10_000)
    logging.getLogger("hirag.gateway.v2").info("ShapeStore initialized (v2)")
except Exception as _e:
    logging.getLogger("hirag.gateway.v2").exception("ShapeStore init failed: %s", _e)
    shape_store = None

_geometry_realtime_task: Optional[asyncio.Task] = None
_geometry_swarm_task: Optional[asyncio.Task] = None
_geometry_swarm_stop: Optional[asyncio.Event] = None
_geometry_swarm_nc = None

_builder_pack_lock = threading.RLock()
_active_builder_packs: Dict[tuple[str, str], Dict[str, Any]] = {}


def _pack_key(namespace: str, modality: Optional[str]) -> tuple[str, str]:
    ns = (namespace or "").strip().lower()
    mod = (modality or "*").strip().lower() or "*"
    return ns, mod


def _set_active_builder_pack(namespace: str, modality: Optional[str], pack: Optional[Dict[str, Any]]) -> None:
    if not namespace:
        return
    key = _pack_key(namespace, modality)
    with _builder_pack_lock:
        if pack is None:
            _active_builder_packs.pop(key, None)
        else:
            _active_builder_packs[key] = copy.deepcopy(pack)
    if shape_store is not None:
        try:
            shape_store.update_builder_pack(namespace, modality, pack)
        except Exception:
            logger.exception("Failed to propagate builder pack metadata to ShapeStore")


def _get_active_builder_pack(namespace: str, modality: Optional[str]) -> Optional[Dict[str, Any]]:
    if not namespace:
        return None
    key = _pack_key(namespace, modality)
    with _builder_pack_lock:
        pack = _active_builder_packs.get(key)
        if pack is not None:
            return copy.deepcopy(pack)
        if modality:
            fallback = _active_builder_packs.get(_pack_key(namespace, None))
            if fallback is not None:
                return copy.deepcopy(fallback)
    return None


def _geometry_context(body: Dict[str, Any], const: Optional[Dict[str, Any]]) -> tuple[str, str]:
    namespace = (body.get("namespace") or "").strip()
    modality = (body.get("modality") or "").strip()
    if const and isinstance(const.get("meta"), dict):
        meta = const.get("meta") or {}
        if not namespace:
            namespace = str(meta.get("namespace") or "").strip()
        if not modality:
            modality = str(
                meta.get("modality")
                or meta.get("mode")
                or meta.get("mod")
                or ""
            ).strip()
    namespace = namespace or NAMESPACE_DEFAULT
    modality = modality or "geometry"
    return namespace, modality


async def _fetch_geometry_pack(
    pack_id: str,
    *,
    rest_url: Optional[str] = None,
    service_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    base_url = (rest_url or SUPABASE_REST_URL or "").strip()
    if not base_url:
        return None
    base = base_url.rstrip("/")
    if not base.endswith("/rest/v1"):
        base = f"{base}/rest/v1"
    url = f"{base}/geometry_parameter_packs"
    params = {
        "select": "id,namespace,modality,pack_type,status,params,population_id,generation,fitness,energy,version,meta",
        "id": f"eq.{pack_id}",
        "limit": "1",
    }
    key = (service_key or SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY or "").strip()
    headers = {"Accept": "application/json"}
    if key:
        headers.update({"apikey": key, "Authorization": f"Bearer {key}"})

    def _request() -> Optional[Dict[str, Any]]:
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Failed to fetch geometry parameter pack %s: %s", pack_id, exc)
            return None
        if isinstance(data, list) and data:
            row = data[0]
            if isinstance(row, dict):
                return row
        return None

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _request)


async def _apply_swarm_meta(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    namespace = (payload.get("namespace") or NAMESPACE_DEFAULT).strip() or NAMESPACE_DEFAULT
    modality = (payload.get("modality") or "geometry").strip() or "geometry"
    status = (payload.get("status") or "").strip().lower()
    pack_id = payload.get("pack_id")
    if not pack_id:
        logger.warning("geometry.swarm.meta payload missing pack_id: %s", payload)
        return

    try:
        geometry_params.clear_cache()
    except Exception:
        logger.exception("Failed to clear geometry parameter cache after swarm meta event")

    if status != "active":
        _set_active_builder_pack(namespace, modality, None)
        logger.info(
            "geometry.swarm.meta.v1 -> deactivated pack %s for %s/%s (status=%s)",
            pack_id,
            namespace,
            modality,
            status or "unknown",
        )
        return

    pack = await _fetch_geometry_pack(pack_id)
    if pack is None or not isinstance(pack, dict):
        pack = {}
    snapshot = copy.deepcopy(pack)
    snapshot.setdefault("id", pack_id)
    snapshot.setdefault("pack_id", pack_id)
    snapshot["status"] = payload.get("status") or pack.get("status")
    snapshot["namespace"] = namespace
    snapshot["modality"] = modality
    for key in ("version", "population_id", "best_fitness", "metrics", "ts"):
        if payload.get(key) is not None:
            snapshot[key] = payload.get(key)
        elif isinstance(pack, dict) and pack.get(key) is not None:
            snapshot.setdefault(key, pack.get(key))

    _set_active_builder_pack(namespace, modality, snapshot)
    logger.info(
        "geometry.swarm.meta.v1 -> activated pack %s for %s/%s", pack_id, namespace, modality
    )


async def _geometry_swarm_worker() -> None:
    global _geometry_swarm_nc, _geometry_swarm_stop
    backoff = max(1.0, GEOMETRY_REALTIME_BACKOFF)
    while True:
        stop_event = asyncio.Event()
        try:
            nc = await nats.connect(servers=[NATS_URL])
            _geometry_swarm_nc = nc
            _geometry_swarm_stop = stop_event

            async def _handler(msg):
                data = msg.data
                payload: Optional[Dict[str, Any]] = None
                if isinstance(data, (bytes, bytearray)):
                    try:
                        payload = json.loads(data.decode())
                    except Exception:
                        logger.warning("Invalid geometry.swarm.meta payload received")
                        return
                elif isinstance(data, dict):
                    payload = data
                if payload is None:
                    return
                try:
                    await _apply_swarm_meta(payload)
                except Exception:
                    logger.exception("Failed to apply geometry.swarm.meta payload")

            await nc.subscribe("geometry.swarm.meta.v1", cb=_handler)
            await stop_event.wait()
            break
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception(
                "NATS geometry.swarm.meta listener error; retrying in %.1fs", backoff
            )
            await asyncio.sleep(backoff)
        finally:
            _geometry_swarm_stop = None
            if _geometry_swarm_nc is not None:
                with contextlib.suppress(Exception):
                    await _geometry_swarm_nc.drain()
                with contextlib.suppress(Exception):
                    await _geometry_swarm_nc.close()
                _geometry_swarm_nc = None
        if stop_event.is_set():
            break

# Optional HRM decoder controller (lazily loads packs per-namespace)
_hrm_controller = HrmDecoderController(get_decoder_pack)

def _hostname_resolves(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        import socket
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        socket.getaddrinfo(host, None)
        return True
    except Exception:
        return False


def _port_reachable(url: str, timeout: float = 2.0) -> bool:
    """Check if the host:port is actually reachable (not just DNS resolution)."""
    try:
        from urllib.parse import urlparse
        import socket
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            return False
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _derive_realtime_url() -> Optional[str]:
    if SUPABASE_REALTIME_DISABLED:
        logger.info("Supabase realtime disabled via env; skipping subscription")
        return None
    # If explicitly provided and resolvable, respect it; otherwise fall back
    if SUPABASE_REALTIME_URL:
        try:
            # Inside container heuristic
            in_container = os.path.exists("/.dockerenv")
        except Exception:
            in_container = False

        if in_container and "api.supabase.internal" in SUPABASE_REALTIME_URL:
            # This hostname typically exists on the host only; containers should use host-gateway.
            # Prefer the internal REST base as the source of truth for host/port.
            rest_base = SUPABASE_REST_INTERNAL_URL or SUPABASE_REST_URL
            if rest_base:
                rb = rest_base.rstrip('/')
                if rb.endswith('/rest/v1'):
                    rb = rb[: -len('/rest/v1')]
                if rb.startswith('https://'):
                    rb = 'wss://' + rb[len('https://'):]
                elif rb.startswith('http://'):
                    rb = 'ws://' + rb[len('http://'):]
                return rb + '/realtime/v1/websocket'
            logger.warning(
                "Rewriting SUPABASE_REALTIME_URL host 'api.supabase.internal' to host-gateway failed; no REST base set"
            )
        else:
            if _port_reachable(SUPABASE_REALTIME_URL):
                return SUPABASE_REALTIME_URL
            # If a custom URL is set but port isn't reachable inside the container,
            # try to derive one from the REST base (host-gateway safe) so we recover automatically.
            logger.info(
                "Configured SUPABASE_REALTIME_URL port not reachable; deriving from REST base instead"
            )
    # Prefer internal host-gateway REST base if present
    rest_base = SUPABASE_REST_INTERNAL_URL or SUPABASE_REST_URL
    if not rest_base:
        return None
    rest = (rest_base or "").rstrip("/")
    if "postgrest" in rest or rest.endswith(":3000"):
        candidate = "ws://realtime:4000/socket/websocket"
        if _port_reachable(candidate):
            return candidate
        logger.info("Supabase realtime service not available on docker network; skipping subscription")
        return None
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

    startup_time = time.monotonic()
    current_backoff = GEOMETRY_REALTIME_BACKOFF

    while True:
        full_url = ws_url
        if full_url.rstrip('/').endswith('/realtime/v1'):
            full_url = full_url.rstrip('/') + '/websocket'
        if "apikey=" not in full_url:
            sep = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{sep}apikey={api_key}&vsn=1.0.0"
        headers = {}
        if SUPABASE_REALTIME_KEY:
            headers["Authorization"] = f"Bearer {SUPABASE_REALTIME_KEY}"
        try:
            async with websockets.connect(
                full_url,
                ping_interval=20,
                ping_timeout=20,
                max_queue=None,
                extra_headers=headers or None,
            ) as ws:
                join_payload = {
                    "topic": "realtime:geometry.cgp.v1",
                    "event": "phx_join",
                    "payload": {
                        "config": {"broadcast": {"ack": False, "self": True}},
                        "access_token": api_key,
                    },
                    "ref": "1",
                }
                await ws.send(json.dumps(join_payload))
                logger.info("Subscribed to Supabase realtime geometry.cgp.v1 channel")
                # Reset backoff on successful connection
                current_backoff = max(1.0, GEOMETRY_REALTIME_BACKOFF)
                heartbeat = asyncio.create_task(_phoenix_heartbeat(ws))
                try:
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError as e:
                            logger.debug("Supabase realtime: failed to parse message: %s", e)
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
        except Exception as exc:
            elapsed = time.monotonic() - startup_time
            if elapsed < GEOMETRY_REALTIME_STARTUP_GRACE:
                # During startup grace period, use WARNING (not ERROR with stack trace)
                # because Supabase realtime may still be initializing - this is expected behavior
                logger.warning(
                    "Supabase realtime not ready (%s: %s); retrying in %.1fs (grace period: %.0fs remaining)",
                    type(exc).__name__,
                    str(exc)[:100],
                    current_backoff,
                    GEOMETRY_REALTIME_STARTUP_GRACE - elapsed,
                )
                # Still log stack trace at DEBUG for troubleshooting unexpected errors
                logger.debug("Stack trace for startup grace period warning:", exc_info=True)
            else:
                logger.exception(
                    "Supabase realtime listener error (%s); retrying in %.1fs",
                    type(exc).__name__,
                    current_backoff,
                )
            await asyncio.sleep(current_backoff)
            # Exponential backoff with cap
            current_backoff = min(current_backoff * 2, GEOMETRY_REALTIME_MAX_BACKOFF)


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
    global _geometry_swarm_task
    if _geometry_swarm_task is None and NATS_URL:
        if hasattr(nats, "connect"):
            _geometry_swarm_task = asyncio.create_task(_geometry_swarm_worker())
            logger.info("NATS geometry.swarm.meta listener started (url=%s)", NATS_URL)
        else:
            logger.info("NATS client unavailable; geometry.swarm.meta listener skipped")


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    global _geometry_realtime_task
    if _geometry_realtime_task is not None:
        _geometry_realtime_task.cancel()
        with contextlib.suppress(Exception):
            await _geometry_realtime_task
        _geometry_realtime_task = None
    global _geometry_swarm_task, _geometry_swarm_stop
    if _geometry_swarm_stop is not None:
        _geometry_swarm_stop.set()
    if _geometry_swarm_task is not None:
        _geometry_swarm_task.cancel()
        with contextlib.suppress(Exception):
            await _geometry_swarm_task
        _geometry_swarm_task = None
    _geometry_swarm_stop = None

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
GAN_SIDECAR_ENABLED = os.environ.get("GAN_SIDECAR_ENABLED", "false").lower()=="true"

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

def _parse_trusted_proxies(raw_entries):
    networks = []
    for raw in raw_entries:
        entry = raw.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                networks.append(ipaddress.ip_network(entry, strict=False))
            else:
                ip_obj = ipaddress.ip_address(entry)
                cidr = "32" if isinstance(ip_obj, ipaddress.IPv4Address) else "128"
                networks.append(ipaddress.ip_network(f"{ip_obj}/{cidr}", strict=False))
        except ValueError:
            logger.warning("Ignoring invalid trusted proxy entry: %s", entry)
    return networks


_TRUSTED_PROXY_NETWORKS = _parse_trusted_proxies(TRUSTED_PROXY_SOURCES)


def _trusted_proxy(host: Optional[str]) -> bool:
    if not host or not _TRUSTED_PROXY_NETWORKS:
        return False
    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        logger.debug("Request client host is not a valid IP: %s", host)
        return False
    return any(ip_obj in network for network in _TRUSTED_PROXY_NETWORKS)


def _client_ip(request: Request) -> str:
    peer_ip = request.client.host if request.client else None
    if peer_ip and _trusted_proxy(peer_ip):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            candidate = xff.split(",")[0].strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                logger.debug("Ignoring invalid X-Forwarded-For entry: %s", candidate)
    return peer_ip or "127.0.0.1"

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


def _build_media_url(media: Dict[str, Any]) -> Optional[str]:
    modality = (media.get("modality") or "").lower()
    ref_id = media.get("ref_id") or media.get("uid") or ""
    if modality == "video" and ref_id:
        video_id = ref_id
        if ref_id.startswith("yt_"):
            video_id = ref_id.split("_", 1)[1]
        base = f"https://www.youtube.com/watch?v={quote_plus(video_id)}"
        t_start = media.get("t_start") or media.get("start")
        try:
            seconds = int(float(t_start)) if t_start is not None else None
        except (TypeError, ValueError):
            seconds = None
        return f"{base}&t={seconds}s" if seconds else base
    return None


def _enrich_mindmap_item(constellation_id: str, point: Dict[str, Any], media: Dict[str, Any]) -> Dict[str, Any]:
    media_url = _build_media_url(media)
    t_start = media.get("t_start") or media.get("start")
    try:
        timestamp = float(t_start) if t_start is not None else None
    except (TypeError, ValueError):
        timestamp = None
    notebook_payload = {
        "constellation_id": constellation_id,
        "point_id": point.get("id"),
        "title": (point.get("text") or "").strip()[:120],
        "media_url": media_url,
        "timestamp": timestamp,
        "modality": (media.get("modality") or point.get("modality") or "").lower(),
    }
    return {
        "point": point,
        "media": media,
        "media_url": media_url,
        "timestamp": timestamp,
        "notebook": notebook_payload,
    }

@app.get("/hirag/admin/stats")
def stats(request: Request):
    if os.environ.get("SMOKE_ALLOW_ADMIN_STATS", "false").lower() != "true":
        # Enforce admin tailscale guard unless explicitly relaxed for local smokes
        require_admin_tailscale(request)
    cuda = None
    try:
        import torch  # type: ignore
        cuda = bool(torch.cuda.is_available())
    except Exception:
        cuda = None
    # Prefer label override for reporting
    model_report = _rerank_model_label or RERANK_MODEL
    return {
        "rerank_enabled": RERANK_ENABLE,
        "rerank_model": (model_report or None) if RERANK_ENABLE else None,
        "rerank_loaded": _reranker is not None,
        "cuda": cuda,
        "use_meili": USE_MEILI,
        "graph": {"boost": GRAPH_BOOST, "types": len(_warm_entities), "last_refresh": _warm_last},
        "alpha": ALPHA,
        "collection": COLL
    }


@app.get("/hirag/admin/rerank-status")
def admin_rerank_status(request: Request):
    if os.environ.get("SMOKE_ALLOW_ADMIN_STATS", "false").lower() != "true":
        require_admin_tailscale(request)
    status = get_rerank_status()
    status["model_report"] = _rerank_model_label or status["model"]
    return status

@app.post("/hirag/admin/reranker/model/label")
def set_rerank_model_label(body: Dict[str, Any], request: Request):
    # Allow local smoke to set a label for reporting without changing the loaded model
    if os.environ.get("SMOKE_ALLOW_ADMIN_STATS", "false").lower() != "true":
        require_admin_tailscale(request)
    global _rerank_model_label
    label = (body or {}).get("label") or ""
    _rerank_model_label = label.strip() or None
    return {"ok": True, "rerank_model_label": _rerank_model_label}

@app.post("/hirag/query", response_model=QueryResp)
def hirag_query(req: QueryReq = Body(...), request: Request = None, _=Depends(require_tailscale)):
    client_ip = None
    try:
        client_ip = _client_ip(request) if request is not None else None
    except Exception:
        client_ip = None
    logger.warning("hirag.query incoming namespace=%s ip=%s", getattr(req, "namespace", None), client_ip)
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


@app.get("/mindmap/{constellation_id}")
def mindmap_route(
    constellation_id: str,
    modalities: str = "text,video,audio,doc,image",
    minProj: float = 0.5,
    minConf: float = 0.5,
    limit: int = 200,
    offset: int = 0,
    enrich: bool = True,
    _=Depends(require_tailscale),
):
    if driver is None:
        raise HTTPException(503, "Neo4j unavailable")
    mods = [m.strip() for m in modalities.split(",") if m.strip()]
    if not mods:
        raise HTTPException(400, "At least one modality is required")
    if limit <= 0:
        raise HTTPException(400, "limit must be positive")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")
    db_limit = limit + 1
    stats_map: Dict[str, int] = {}
    total_query = (
        "MATCH (c:Constellation {id:$cid})-[:HAS]->(p:Point) "
        "WHERE p.modality IN $mods AND coalesce(p.proj,0.0) >= $minProj "
        "AND coalesce(p.conf,0.0) >= $minConf "
        "RETURN count(*) AS total"
    )
    stats_query = (
        "MATCH (c:Constellation {id:$cid})-[:HAS]->(p:Point) "
        "WHERE p.modality IN $mods AND coalesce(p.proj,0.0) >= $minProj "
        "AND coalesce(p.conf,0.0) >= $minConf "
        "RETURN coalesce(p.modality,'unknown') AS modality, count(*) AS count"
    )
    query = (
        "MATCH (c:Constellation {id:$cid})-[:HAS]->(p:Point)-[:LOCATES]->(m:MediaRef) "
        "WHERE p.modality IN $mods AND coalesce(p.proj,0.0) >= $minProj "
        "AND coalesce(p.conf,0.0) >= $minConf "
        "RETURN p{.*, id:p.id} AS point, m{.*, uid:m.uid} AS media "
        "ORDER BY p.proj DESC SKIP $offset LIMIT $limit"
    )
    try:
        with driver.session() as session:
            total_result = session.run(
                total_query,
                cid=constellation_id,
                mods=mods,
                minProj=minProj,
                minConf=minConf,
            )
            total_row = next(iter(total_result), {"total": 0})
            total = int(total_row.get("total") or 0)
            stats_rows = session.run(
                stats_query,
                cid=constellation_id,
                mods=mods,
                minProj=minProj,
                minConf=minConf,
            )
            stats_map: Dict[str, int] = {}
            for row in stats_rows:
                mod = str(row.get("modality") or "unknown").lower()
                stats_map[mod] = int(row.get("count") or 0)
            records = session.run(
                query,
                cid=constellation_id,
                mods=mods,
                minProj=minProj,
                minConf=minConf,
                limit=db_limit,
                offset=offset,
            )
            raw_items = [(rec["point"], rec["media"]) for rec in records]
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("mindmap query failed")
        raise HTTPException(500, f"mindmap query failed: {exc}")
    has_more = len(raw_items) > limit
    trimmed = raw_items[:limit]
    if enrich:
        items = [
            _enrich_mindmap_item(constellation_id, point or {}, media or {})
            for point, media in trimmed
        ]
    else:
        items = [{"point": point, "media": media} for point, media in trimmed]
    returned = len(items)
    remaining = max(total - (offset + returned), 0)
    return {
        "items": items,
        "offset": offset,
        "limit": limit,
        "returned": returned,
        "total": total,
        "remaining": remaining,
        "has_more": has_more,
        "stats": {"per_modality": stats_map},
    }

def _tensorzero_rerank(query: str, pool: List[Dict[str, Any]]) -> Optional[List[float]]:
    base = TENSORZERO_BASE_URL.rstrip("/")
    if not base or not pool:
        return None
    url = f"{base}/functions/{TENSORZERO_RERANK_FUNCTION}/invoke"
    payload = {
        "query": query,
        "documents": [p.get("text", "") for p in pool],
    }
    headers = {"Content-Type": "application/json"}
    if TENSORZERO_API_KEY:
        headers["Authorization"] = f"Bearer {TENSORZERO_API_KEY}"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=TENSORZERO_RERANK_TIMEOUT)
        if not resp.ok:
            logger.warning(
                "tensorzero rerank request failed status=%s body=%s", resp.status_code, resp.text[:200]
            )
            return None
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        scores = data.get("scores") or data.get("data")
        if isinstance(scores, list):
            try:
                return [float(s) for s in scores]
            except (TypeError, ValueError):
                return None
    except Exception:
        logger.exception("tensorzero rerank invocation error")
    return None


def _get_reranker():
    global _reranker
    if _reranker is not None:
        return _reranker
    if not RERANK_ENABLE:
        return None
    try:
        use_fp16 = _RERANK_FP16_EFFECTIVE
        _reranker = FlagReranker(RERANK_MODEL_RESOLVED, use_fp16=use_fp16)
        if DEVICE == "cuda" and hasattr(_reranker, "model"):
            _reranker.model = _reranker.model.to("cuda")  # type: ignore[attr-defined]
        return _reranker
    except Exception as e:
        logger.exception("Reranker init failed")
        return None


# --- GAN Sidecar loader -------------------------------------------------
_gan_sidecar = None


def _get_gan_sidecar():
    global _gan_sidecar
    if _gan_sidecar is not None:
        return _gan_sidecar
    module_name = "hirag_gateway_v2.sidecars.gan_checker"
    module = sys.modules.get(module_name)
    if module is None:
        sidecar_path = Path(__file__).resolve().parent / "sidecars" / "gan_checker.py"
        if not sidecar_path.exists():
            logger.warning("GAN sidecar module missing at %s", sidecar_path)
            _gan_sidecar = None
            return None
        try:
            spec = importlib.util.spec_from_file_location(module_name, sidecar_path)
            if spec is None or spec.loader is None:
                raise ImportError("unable to load gan_checker spec")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception:
            logger.exception("Failed to import GAN sidecar module")
            _gan_sidecar = None
            return None
    try:
        _gan_sidecar = module.GanSidecar()
    except Exception:
        logger.exception("GAN sidecar init failed")
        _gan_sidecar = None
    return _gan_sidecar


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
    context_body = dict(body)
    context_body.setdefault("modality", "text")
    namespace, modality = _geometry_context(context_body, const)
    builder_pack = _get_active_builder_pack(namespace, modality)
    namespace = str(
        body.get("namespace")
        or (const.get("namespace") if isinstance(const, dict) and const.get("namespace") else NAMESPACE_DEFAULT)
    )
    pts: List[Dict[str, Any]] = []
    if const:
        for p in const.get("points", []) or []:
            cid = p.get("id")
            if not cid:
                continue
            pts.append({
                "id": cid,
                "text": p.get("text"),
                "proj": p.get("proj"),
                "conf": p.get("conf"),
                "meta": p.get("meta"),
                "ref_id": p.get("ref_id") or p.get("doc_id") or p.get("video_id"),
            })
    pts.sort(key=lambda x: (x.get("conf") or 0.0, x.get("proj") or 0.0), reverse=True)
    top_pts = pts[:k]

    # Mode handling: "learned" (T5 summarization), "swarm" (EvoSwarm GAN), or default (geometry points)
    if mode == "learned":
        try:
            from transformers import pipeline  # type: ignore
        except (ImportError, ModuleNotFoundError) as exc:
            raise HTTPException(500, f"transformers not available: {type(exc).__name__}")
        texts = []
        cb = _load_codebook(CHIT_CODEBOOK_PATH)
        for rec in cb[: min(64, len(cb))]:
            t = rec.get("text") or rec.get("summary")
            if t:
                texts.append(t)
        if const:
            s = const.get("summary")
            if s:
                texts.insert(0, s)
        if not texts:
            raise HTTPException(400, "no codebook or constellation text available")
        nlp = pipeline("summarization", model=CHIT_T5_MODEL)
        out = nlp("\n".join(texts)[:4000], max_length=128, min_length=32, do_sample=False)
        summary = out[0].get("summary_text", "")
        # Apply HRM refinement to learned mode summary
        summary, hrm_info = _hrm_controller.maybe_refine(summary, namespace=namespace)
        return {
            "mode": mode,
            "summary": summary,
            "used": len(texts),
            "hrm": hrm_info,
            "namespace": namespace,
            "modality": modality,
            "builder_pack": builder_pack,
        }

    elif mode == "swarm":
        # EvoSwarm mode: GAN sidecar reviews and re-ranks candidates
        sidecar = _get_gan_sidecar()
        accept_threshold = float(body.get("accept_threshold", 0.55))
        max_edits = int(body.get("max_edits", 1))
        if sidecar is None:
            return {
                "mode": mode,
                "raw_points": top_pts,
                "selected": top_pts[0] if top_pts else None,
                "candidates": [],
                "telemetry": {
                    "enabled": GAN_SIDECAR_ENABLED,
                    "decision": "unavailable",
                    "threshold": accept_threshold,
                },
                "namespace": namespace,
                "modality": modality,
                "builder_pack": builder_pack,
            }
        review = sidecar.review_text_candidates(
            top_pts,
            enabled=GAN_SIDECAR_ENABLED,
            max_edits=max(0, max_edits),
            accept_threshold=accept_threshold,
        )
        review["mode"] = mode
        review["raw_points"] = top_pts
        review["namespace"] = namespace
        review["modality"] = modality
        review["builder_pack"] = builder_pack
        return review

    else:
        # Default geometry mode: return top-k points with HRM status
        # Use pre-computed top_pts (already sorted and sliced at line 1650)
        hrm_info = _hrm_controller.status(namespace)
        return {
            "mode": mode,
            "points": top_pts,
            "hrm": hrm_info,
            "namespace": namespace,
            "modality": modality,
            "builder_pack": builder_pack,
        }

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
    mode = (body.get("mode") or "geometry").lower()
    const_id = body.get("constellation_id")
    images = body.get("images") or []
    if not images:
        raise HTTPException(400, "images list required")
    const = shape_store.get_constellation(const_id) if (shape_store and const_id) else None
    text = body.get("text") or (const.get("summary") if const else None)
    if not text:
        raise HTTPException(400, "text or constellation summary required for anchor")
    context_body = dict(body)
    context_body.setdefault("modality", "image")
    namespace, modality = _geometry_context(context_body, const)
    builder_pack = _get_active_builder_pack(namespace, modality)
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
        return {
            "ranked": [{"url": u, "score": float(s)} for u, s in ranked],
            "namespace": namespace,
            "modality": modality,
            "builder_pack": builder_pack,
        }
        payload = {"mode": mode, "ranked": [{"url": u, "score": float(s)} for u,s in ranked]}
        if mode == "swarm":
            sidecar = _get_gan_sidecar()
            accept_threshold = float(body.get("accept_threshold", 0.55))
            max_edits = int(body.get("max_edits", 0))
            if sidecar is None:
                payload["swarm"] = {
                    "selected": None,
                    "candidates": [],
                    "telemetry": {
                        "enabled": GAN_SIDECAR_ENABLED,
                        "decision": "unavailable",
                        "threshold": accept_threshold,
                    },
                }
            else:
                captions = body.get("captions") or {}
                candidates = []
                for item in payload["ranked"]:
                    url = item["url"]
                    caption = captions.get(url) or text or f"Image candidate {url}"
                    candidates.append({"id": url, "text": caption})
                payload["swarm"] = sidecar.review_text_candidates(
                    candidates,
                    enabled=GAN_SIDECAR_ENABLED,
                    max_edits=max(0, max_edits),
                    accept_threshold=accept_threshold,
                )
        return payload
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
    mode = (body.get("mode") or "geometry").lower()
    const_id = body.get("constellation_id")
    audios = body.get("audios") or []
    if not audios:
        raise HTTPException(400, "audios list required")
    const = shape_store.get_constellation(const_id) if (shape_store and const_id) else None
    text = body.get("text") or (const.get("summary") if const else None)
    if not text:
        raise HTTPException(400, "text or constellation summary required for anchor")
    context_body = dict(body)
    context_body.setdefault("modality", "audio")
    namespace, modality = _geometry_context(context_body, const)
    builder_pack = _get_active_builder_pack(namespace, modality)
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
        return {
            "ranked": [{"path": u, "score": float(s)} for u, s in ranked],
            "namespace": namespace,
            "modality": modality,
            "builder_pack": builder_pack,
        }
        payload = {"mode": mode, "ranked": [{"path": u, "score": float(s)} for u,s in ranked]}
        if mode == "swarm":
            sidecar = _get_gan_sidecar()
            accept_threshold = float(body.get("accept_threshold", 0.55))
            max_edits = int(body.get("max_edits", 0))
            if sidecar is None:
                payload["swarm"] = {
                    "selected": None,
                    "candidates": [],
                    "telemetry": {
                        "enabled": GAN_SIDECAR_ENABLED,
                        "decision": "unavailable",
                        "threshold": accept_threshold,
                    },
                }
            else:
                captions = body.get("captions") or {}
                candidates = []
                for item in payload["ranked"]:
                    path = item["path"]
                    caption = captions.get(path) or text or f"Audio candidate {path}"
                    candidates.append({"id": path, "text": caption})
                payload["swarm"] = sidecar.review_text_candidates(
                    candidates,
                    enabled=GAN_SIDECAR_ENABLED,
                    max_edits=max(0, max_edits),
                    accept_threshold=accept_threshold,
                )
        return payload
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
                    raw_anchor = const.get("anchor")
                    anchor_enc = const.get("anchor_enc")
                    anchor: Optional[List[float]] = None
                    if isinstance(raw_anchor, (list, tuple)) and len(raw_anchor) > 0:
                        anchor = [float(x) for x in raw_anchor]
                    else:
                        spectrum = const.get("spectrum")
                        if isinstance(spectrum, list) and spectrum:
                            anchor = [float(x) for x in spectrum[:3]]
                            while len(anchor) < 3:
                                anchor.append(0.0)
                        else:
                            anchor = [0.0, 0.0, 0.0]
                    dim = len(anchor)
                    cur.execute(
                        """
                        INSERT INTO public.anchors(kind, dim, anchor, anchor_enc, meta)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            'multi',
                            int(dim),
                            anchor,
                            json.dumps(anchor_enc) if anchor_enc else None,
                            json.dumps({})
                        )
                    )
                    anchor_id = cur.fetchone()[0]
                    spectrum = const.get("spectrum") if isinstance(const.get("spectrum"), list) else None
                    radial = const.get("radial_minmax") if isinstance(const.get("radial_minmax"), list) else [None, None]
                    summary = const.get("summary")
                    # insert constellation (preserve CGP/meta provenance if present)
                    const_meta = {}
                    try:
                        if isinstance(const.get("meta"), dict):
                            const_meta.update(const.get("meta") or {})
                    except Exception:
                        pass
                    try:
                        if isinstance(cgp.get("meta"), dict):
                            # Only carry selected keys to avoid bloat
                            for k in ("namespace", "pack_id", "pack_version", "population_id", "builder_pack"):
                                v = cgp["meta"].get(k)
                                if v is not None:
                                    const_meta[k] = v
                    except Exception:
                        pass
                    cur.execute(
                        """
                        INSERT INTO public.constellations(anchor_id, summary, radial_min, radial_max, spectrum, meta)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (anchor_id, summary, radial[0] if radial else None, radial[1] if radial else None, spectrum, json.dumps(const_meta))
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
