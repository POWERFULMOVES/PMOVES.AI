import os, re, time, threading, ipaddress, math, requests, logging, json, sys, io, socket
import urllib3
from pathlib import Path
from urllib.parse import urlparse

# ensure repo root is on sys.path for importing tools/* when running from service folder
try:
    _repo_root = Path(__file__).resolve().parents[2]
    if str(_repo_root) not in sys.path:
        sys.path.append(str(_repo_root))
except Exception:
    pass
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from services.common.geometry_params import get_decoder_pack
from services.common.hrm_sidecar import HrmDecoderController
from sentence_transformers import SentenceTransformer
try:
    from sentence_transformers import CrossEncoder  # for optional rerank
except Exception:
    CrossEncoder = None  # lazy error if rerank requested
from rapidfuzz import fuzz
from neo4j import GraphDatabase

QDRANT_URL = os.environ.get("QDRANT_URL","http://qdrant:6333")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION","pmoves_chunks")
SENTENCE_MODEL = os.environ.get("SENTENCE_MODEL","all-MiniLM-L6-v2")
EMBEDDING_BACKEND = os.environ.get("EMBEDDING_BACKEND", os.environ.get("EXTRACT_WORKER_EMBEDDING_BACKEND", "sentence-transformers")).lower()
USE_OLLAMA_EMBED = EMBEDDING_BACKEND == "ollama" or os.environ.get("USE_OLLAMA_EMBED","false").lower()=="true"
USE_TENSORZERO_EMBED = EMBEDDING_BACKEND == "tensorzero"
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "qwen3-embedding:4b")
TENSORZERO_BASE_URL = os.environ.get("TENSORZERO_BASE_URL", "http://tensorzero-gateway:3000")
TENSORZERO_EMBED_MODEL = os.environ.get("TENSORZERO_EMBED_MODEL", "tensorzero::embedding_model_name::qwen3_embedding_4b_local")
_raw_ollama_url = os.environ.get("OLLAMA_URL","http://ollama:11434")
if not urlparse(_raw_ollama_url).scheme in ("http", "https"):
    raise ValueError(f"OLLAMA_URL must use http/https scheme")
OLLAMA_URL = _raw_ollama_url
HTTP_PORT = int(os.environ.get("HIRAG_HTTP_PORT","8086"))
NEO4J_URL = (os.environ.get("NEO4J_URL","bolt://neo4j:7687") or "").strip()
NEO4J_USER = os.environ.get("NEO4J_USER","neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD","neo4j")
GRAPH_BOOST = float(os.environ.get("GRAPH_BOOST","0.15"))
ENTITY_CACHE_TTL = int(os.environ.get("ENTITY_CACHE_TTL","60"))
ENTITY_CACHE_MAX = int(os.environ.get("ENTITY_CACHE_MAX","1000"))
NEO4J_DICT_REFRESH_SEC = int(os.environ.get("NEO4J_DICT_REFRESH_SEC","60"))
NEO4J_DICT_LIMIT = int(os.environ.get("NEO4J_DICT_LIMIT","50000"))
USE_MEILI = os.environ.get("USE_MEILI","false").lower()=="true"
MEILI_URL = os.environ.get("MEILI_URL","http://meilisearch:7700")
MEILI_API_KEY = os.environ.get("MEILI_API_KEY","master_key")
TAILSCALE_ONLY = os.environ.get("TAILSCALE_ONLY","true").lower()=="true"
TAILSCALE_ADMIN_ONLY = os.environ.get("TAILSCALE_ADMIN_ONLY","true").lower()=="true"
TAILSCALE_CIDRS = [c.strip() for c in os.environ.get("TAILSCALE_CIDRS","100.64.0.0/10").split(",") if c.strip()]
TRUSTED_PROXY_SOURCES = [c.strip() for c in os.environ.get("HIRAG_TRUSTED_PROXIES", "").split(",") if c.strip()]
NAMESPACE_DEFAULT = os.environ.get("INDEXER_NAMESPACE", "pmoves")

# --- Optional Reranking (GPU preferred, CPU fallback) ---
RERANK_ENABLE = os.environ.get("RERANK_ENABLE", "false").lower() == "true"
RERANK_MODEL = os.environ.get("RERANK_MODEL", "BAAI/bge-reranker-base")
RERANK_TOPN = int(os.environ.get("RERANK_TOPN", "50"))
RERANK_K = int(os.environ.get("RERANK_K", "10"))

app = FastAPI(title="PMOVES Hi-RAG Gateway")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# basic logging for easier debugging in container logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hirag.gateway")

qdrant = QdrantClient(url=QDRANT_URL, timeout=20.0)


def _qdrant_search(
    *,
    collection_name: str,
    query_vector: List[float],
    limit: int,
    query_filter: Optional[Filter],
    with_payload: bool = True,
    with_vectors: bool = False,
):
    """Handle qdrant-client API drift (`search` vs `query_points`)."""
    if hasattr(qdrant, "search"):
        return qdrant.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=with_payload,
            with_vectors=with_vectors,
        )

    if hasattr(qdrant, "query_points"):
        kwargs = {
            "collection_name": collection_name,
            "limit": limit,
            "query_filter": query_filter,
            "with_payload": with_payload,
            "with_vectors": with_vectors,
        }
        try:
            resp = qdrant.query_points(query=query_vector, **kwargs)
        except TypeError:
            resp = qdrant.query_points(vector=query_vector, **kwargs)
        if isinstance(resp, list):
            return resp
        points = getattr(resp, "points", None)
        if isinstance(points, list):
            return points
        result = getattr(resp, "result", None)
        if isinstance(result, list):
            return result
        if isinstance(resp, dict):
            dict_points = resp.get("points")
            if isinstance(dict_points, list):
                return dict_points
            dict_result = resp.get("result")
            if isinstance(dict_result, list):
                return dict_result
        return []

    if hasattr(qdrant, "search_points"):
        resp = qdrant.search_points(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=with_payload,
            with_vectors=with_vectors,
        )
        if isinstance(resp, list):
            return resp
        result = getattr(resp, "result", None)
        if isinstance(result, list):
            return result
        return []

    raise AttributeError("qdrant client has no compatible search/query API")

# Optional Neo4j: run even if service is not present
driver = None
if NEO4J_URL:
    try:
        driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))
    except Exception:
        logger.warning("Neo4j unavailable at %s; disabling graph boost", NEO4J_URL)
        driver = None

# --- Geometry Bus ShapeStore (in-memory) ---
try:
    from services.common.shape_store import ShapeStore
    shape_store = ShapeStore(capacity=10_000)
    logger.info("ShapeStore initialized with capacity 10000")
except Exception as e:
    logger.exception("Failed to initialize ShapeStore: %s", e)
    shape_store = None

_hrm_controller = HrmDecoderController(get_decoder_pack)

# --- CHIT security and decode flags ---
CHIT_REQUIRE_SIGNATURE = os.environ.get("CHIT_REQUIRE_SIGNATURE", "false").lower() == "true"
CHIT_PASSPHRASE = os.environ.get("CHIT_PASSPHRASE", "")
CHIT_DECRYPT_ANCHORS = os.environ.get("CHIT_DECRYPT_ANCHORS", "false").lower() == "true"
CHIT_CODEBOOK_PATH = os.environ.get("CHIT_CODEBOOK_PATH", "datasets/structured_dataset.jsonl")
CHIT_DECODE_TEXT = os.environ.get("CHIT_DECODE_TEXT", "false").lower() == "true"
CHIT_DECODE_IMAGE = os.environ.get("CHIT_DECODE_IMAGE", "false").lower() == "true"
CHIT_DECODE_AUDIO = os.environ.get("CHIT_DECODE_AUDIO", "false").lower() == "true"
CHIT_CLIP_MODEL = os.environ.get("CHIT_CLIP_MODEL", "clip-ViT-B-32")
CHIT_IMAGE_FETCH_ALLOW_PRIVATE = os.environ.get("CHIT_IMAGE_FETCH_ALLOW_PRIVATE", "false").lower() == "true"
CHIT_IMAGE_FETCH_ALLOWED_HOSTS = {
    host.strip().lower()
    for host in os.environ.get("CHIT_IMAGE_FETCH_ALLOWED_HOSTS", "").split(",")
    if host.strip()
}

_codebook_cache = None
_codebook_mtime = None
_clip_model = None
_clip_lock = threading.Lock()
_clap_model = None
_clap_lock = threading.Lock()
_cross_encoder = None
_cross_lock = threading.Lock()

def _load_codebook(path: str):
    import os
    global _codebook_cache, _codebook_mtime
    try:
        st = os.stat(path)
        if _codebook_cache is not None and _codebook_mtime == st.st_mtime:
            return _codebook_cache
        items = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except Exception:
                    continue
        _codebook_cache = items
        _codebook_mtime = st.st_mtime
        return items
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.exception("codebook load error")
        return []

_model = None
def embed_query(text: str):
    global _model
    if USE_TENSORZERO_EMBED:
        try:
            r = requests.post(
                f"{TENSORZERO_BASE_URL}/openai/v1/embeddings",
                json={"model": TENSORZERO_EMBED_MODEL, "input": text},
                timeout=30,
            )
            if not r.ok:
                logger.error("TensorZero embed error: %s", r.text[:300])
                raise HTTPException(502, f"TensorZero embed error: {r.status_code}")
            return r.json()["data"][0]["embedding"]
        except requests.RequestException as e:
            logger.exception("TensorZero embed request failed")
            raise HTTPException(502, f"TensorZero embed request failed: {e}")
    if USE_OLLAMA_EMBED:
        try:
            r = requests.post(f"{OLLAMA_URL}/api/embeddings", json={"model": OLLAMA_EMBED_MODEL, "prompt": text}, timeout=30)
            if not r.ok:
                logger.error("Ollama embed bad response: %s", r.text[:300])
                raise HTTPException(502, f"Ollama embed error: {r.status_code}")
            return r.json().get("embedding")
        except requests.RequestException as e:
            logger.exception("Ollama request failed")
            raise HTTPException(502, f"Ollama request failed: {e}")
    if _model is None:
        try:
            _model = SentenceTransformer(SENTENCE_MODEL)
        except Exception as e:
            logger.exception("Failed to load sentence transformer model %s", SENTENCE_MODEL)
            raise HTTPException(500, f"SentenceTransformer load error: {e}")
    try:
        emb = _model.encode([text], normalize_embeddings=True)
        return emb.tolist()[0]
    except Exception as e:
        logger.exception("SentenceTransformer encode error")
        raise HTTPException(500, f"Embedding encode error: {e}")


def _get_clip_model():
    global _clip_model
    if _clip_model is None:
        with _clip_lock:
            if _clip_model is None:
                try:
                    _clip_model = SentenceTransformer(CHIT_CLIP_MODEL)
                except Exception as e:
                    logger.exception("Failed to load CLIP model %s", CHIT_CLIP_MODEL)
                    raise HTTPException(500, f"CLIP model load error: {e}")
    return _clip_model


def _get_clap_model():
    global _clap_model
    if _clap_model is None:
        with _clap_lock:
            if _clap_model is None:
                try:
                    from laion_clap import CLAP_Module  # type: ignore
                except Exception:
                    raise HTTPException(500, "missing laion-clap/torch; install extras and set CHIT_DECODE_AUDIO=true")
                try:
                    model = CLAP_Module(enable_fusion=True)
                    model.load_ckpt()
                    _clap_model = model
                except HTTPException:
                    raise
                except Exception as e:
                    logger.exception("Failed to initialize CLAP model")
                    raise HTTPException(500, f"CLAP model load error: {e}")
    return _clap_model


def _get_cross_encoder():
    global _cross_encoder
    if not RERANK_ENABLE:
        return None
    if CrossEncoder is None:
        logger.warning("CrossEncoder not available; disabling rerank")
        return None
    if _cross_encoder is None:
        with _cross_lock:
            if _cross_encoder is None:
                try:
                    # Auto-select CUDA if available
                    device = "cuda"
                    try:
                        import torch  # type: ignore
                        device = "cuda" if torch.cuda.is_available() else "cpu"
                    except Exception:
                        device = "cpu"
                    _cross_encoder = CrossEncoder(RERANK_MODEL, device=device)
                except Exception as e:
                    logger.warning("Failed to load CrossEncoder %s; disabling rerank: %s", RERANK_MODEL, e)
                    return None
    return _cross_encoder

def hybrid_score(vec_score: float, lex_score: float, alpha: float=0.7) -> float:
    return alpha*vec_score + (1.0-alpha)*lex_score

_cache_entities = {}
_cache_order = []

def cache_get(tok: str):
    ent = _cache_entities.get(tok)
    if not ent: return None
    ts, vals = ent
    if time.time() - ts > ENTITY_CACHE_TTL:
        return None
    return vals

def cache_set(tok: str, vals):
    _cache_entities[tok] = (time.time(), vals)
    _cache_order.append(tok)
    while len(_cache_order) > ENTITY_CACHE_MAX:
        old = _cache_order.pop(0)
        _cache_entities.pop(old, None)

_warm_entities = {}
_warm_last = 0.0

def refresh_warm_dictionary():
    global _warm_entities, _warm_last
    if driver is None:
        _warm_entities = {}
        _warm_last = time.time()
        return
    try:
        tmp = {}
        with driver.session() as s:
            recs = s.run(
                (
                    # Avoid Neo4j "UnknownLabelWarning" when the graph hasn't been seeded yet.
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
    except Exception as e:
        logger.exception("warm dictionary error")

def warm_loop():
    while True:
        try: refresh_warm_dictionary()
        except Exception as e: print("warm loop error:", e)
        time.sleep(max(15, NEO4J_DICT_REFRESH_SEC))

import threading as _t
if driver is not None:
    _t.Thread(target=warm_loop, daemon=True).start()

def graph_terms(query: str, limit: int = 8, entity_types=None):
    # split on non-word characters
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
                if len(out) >= limit: return list(out)[:limit]
    return list(out)[:limit]

def meili_lexical(query, namespace, limit):
    if not USE_MEILI: return {}
    try:
        headers={'Authorization': f'Bearer {MEILI_API_KEY}'} if MEILI_API_KEY else {}
        payload={'q': query, 'limit': max(10, limit*3), 'filter': [f"namespace = '{namespace}'"]}
        r = requests.post(f"{MEILI_URL}/indexes/pmoves_chunks/search", json=payload, headers=headers, timeout=10)
        if not r.ok: return {}
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


def _host_is_private_or_internal(hostname: str) -> bool:
    host = (hostname or "").strip().lower()
    if not host:
        return True
    if host in {"localhost"} or host.endswith(".local"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True

    seen: set[str] = set()
    for _, _, _, _, sockaddr in infos:
        ip_raw = sockaddr[0]
        if ip_raw in seen:
            continue
        seen.add(ip_raw)
        try:
            ip_obj = ipaddress.ip_address(ip_raw)
        except ValueError:
            return True
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            return True
    return False


def _validate_remote_image_url(raw_url: Any) -> str:
    url = str(raw_url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(400, f"invalid image URL scheme: {parsed.scheme or '<none>'}")
    if not parsed.hostname:
        raise HTTPException(400, "invalid image URL host")
    if parsed.username or parsed.password:
        raise HTTPException(400, "image URL credentials are not allowed")

    host = parsed.hostname.lower()
    if CHIT_IMAGE_FETCH_ALLOWED_HOSTS and host not in CHIT_IMAGE_FETCH_ALLOWED_HOSTS:
        raise HTTPException(400, f"image host not allowed: {host}")
    if not CHIT_IMAGE_FETCH_ALLOW_PRIVATE and not CHIT_IMAGE_FETCH_ALLOWED_HOSTS:
        if _host_is_private_or_internal(host):
            raise HTTPException(400, f"private/internal image host blocked: {host}")
    return url


def _fetch_remote_image(raw_url: str, *, timeout: int = 20) -> urllib3.HTTPResponse:
    """Validate URL for SSRF and fetch via resolved IP to prevent DNS rebinding.

    Resolves DNS once, validates all IPs against private ranges, then connects
    directly to the validated IP using urllib3 (no second DNS lookup). Sets
    Host header for correct HTTP routing and server_hostname for TLS SNI.
    """
    url = _validate_remote_image_url(raw_url)
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    try:
        addrs = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise HTTPException(400, f"cannot resolve image host: {host}")
    if not addrs:
        raise HTTPException(400, f"no addresses for host: {host}")

    if not CHIT_IMAGE_FETCH_ALLOW_PRIVATE:
        for _, _, _, _, sockaddr in addrs:
            try:
                ip_obj = ipaddress.ip_address(sockaddr[0])
            except ValueError:
                raise HTTPException(400, f"invalid IP for host: {host}")
            if (
                ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local
                or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified
            ):
                raise HTTPException(400, f"private/internal image host blocked: {host}")

    req_path = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")
    pool_timeout = urllib3.util.Timeout(connect=10, read=timeout)

    # Deduplicate resolved IPs while preserving order
    seen_ips: set = set()
    unique_ips: list = []
    for _, _, _, _, sockaddr in addrs:
        ip = sockaddr[0]
        if ip not in seen_ips:
            seen_ips.add(ip)
            unique_ips.append(ip)

    # Try each resolved address (handles dual-stack AAAA/A and round-robin DNS)
    last_exc: Optional[Exception] = None
    for resolved_ip in unique_ips:
        if parsed.scheme == "https":
            pool = urllib3.HTTPSConnectionPool(
                resolved_ip, port=port,
                timeout=pool_timeout,
                server_hostname=host,
            )
        else:
            pool = urllib3.HTTPConnectionPool(
                resolved_ip, port=port,
                timeout=pool_timeout,
            )
        try:
            http_resp = pool.request("GET", req_path, headers={"Host": host}, redirect=False)
        except Exception as exc:
            pool.close()
            last_exc = exc
            continue
        pool.close()
        if http_resp.status >= 400:
            raise HTTPException(400, f"remote image fetch failed with HTTP {http_resp.status}")
        if 300 <= http_resp.status < 400:
            raise HTTPException(400, f"redirect responses are not allowed for image URL: {url}")
        return http_resp

    # All resolved addresses failed
    raise HTTPException(400, f"all resolved addresses unreachable for {host}: {last_exc}")


def run_query(query, namespace, k=8, alpha=0.7, graph_boost=GRAPH_BOOST, entity_types=None):
    emb = embed_query(query)
    cond = Filter(must=[FieldCondition(key="namespace", match=MatchValue(value=namespace))])
    topn = max(16, k)
    if RERANK_ENABLE:
        topn = max(RERANK_TOPN, k)
    try:
        sr = _qdrant_search(
            collection_name=QDRANT_COLLECTION,
            query_vector=emb,
            limit=topn,
            query_filter=cond,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as e:
        logger.exception("Qdrant search error")
        raise HTTPException(503, f"Qdrant search error: {e}")

    gterms = set([t.lower() for t in graph_terms(query, entity_types=entity_types)]) if driver is not None and GRAPH_BOOST > 0 else set()
    meili_scores = meili_lexical(query, namespace, k) if USE_MEILI else {}
    prelim = []
    for p in sr:
        txt = p.payload.get("text", "")
        lex = float(meili_scores.get(p.payload.get('chunk_id'), 0.0)) if USE_MEILI else (fuzz.token_set_ratio(query, txt)/100.0)
        vec = float(p.score) if isinstance(p.score, (int, float)) else 0.0
        g_hit = any(term in txt.lower() for term in gterms)
        score = hybrid_score(vec, lex, alpha) + (graph_boost if g_hit else 0.0)
        prelim.append({
            "doc_id": p.payload.get("doc_id"),
            "section_id": p.payload.get("section_id"),
            "chunk_id": p.payload.get("chunk_id"),
            "text": txt,
            "score": float(score),
            "namespace": p.payload.get("namespace"),
            "graph_match": bool(g_hit)
        })

    # Optional rerank using cross-encoder
    if RERANK_ENABLE and prelim:
        ce = _get_cross_encoder()
        if ce is None:
            logger.info("Reranker unavailable; returning preliminary scores")
            prelim.sort(key=lambda x: x["score"], reverse=True)
            return prelim[:k]
        try:
            pairs = [(query, r["text"] or "") for r in prelim]
            rr = ce.predict(pairs)
            for r, s in zip(prelim, rr):
                r["rerank_score"] = float(s)
            prelim.sort(key=lambda x: x.get("rerank_score", x.get("score", 0.0)), reverse=True)
            return prelim[:max(k, RERANK_K)]
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Rerank error; falling back to preliminary scores")
            # fall through to sort by prelim score

    prelim.sort(key=lambda x: x["score"], reverse=True)
    return prelim[:k]

@app.post("/hirag/query")
def http_query(body: dict, _=Depends(require_tailscale)):
    # validate payload
    try:
        q = body.get("query", "")
        ns = body.get("namespace", "default")
        k = int(body.get("k", 8))
        if k <= 0:
            raise ValueError("k must be > 0")
        alpha = float(body.get("alpha", 0.7))
        if not (0.0 <= alpha <= 1.0):
            raise ValueError("alpha must be between 0.0 and 1.0")
        gb = float(body.get("graph_boost", GRAPH_BOOST))
        et = body.get("entity_types")
    except Exception as e:
        logger.exception("Invalid query payload")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    # run query and log request/results for observability
    try:
        logger.info("/hirag/query received: q=%s namespace=%s k=%d alpha=%s entity_types=%s", q if len(q) < 200 else q[:200] + "...", ns, k, alpha, et)
        results = run_query(q, ns, k, alpha, gb, et)
        logger.info("/hirag/query results count=%d for q=%s", len(results), q if len(q) < 80 else q[:80] + "...")
        return {"query": q, "results": results}
    except HTTPException:
        # re-raise HTTPExceptions from lower layers
        raise
    except Exception as e:
        logger.exception("Unhandled error running query")
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

@app.get("/hirag/admin/stats")
def hirag_admin_stats(_=Depends(require_admin_tailscale)):
    return {
        "entity_cache": {"keys": len(_cache_entities), "ttl": ENTITY_CACHE_TTL, "max": ENTITY_CACHE_MAX},
        "warm_dictionary": {"types": len(_warm_entities), "entries": int(sum(len(s) for s in _warm_entities.values())), "last_refresh": _warm_last},
        "config": {"EMBEDDING_BACKEND": EMBEDDING_BACKEND, "USE_MEILI": USE_MEILI, "GRAPH_BOOST": GRAPH_BOOST, "NEO4J_DICT_REFRESH_SEC": NEO4J_DICT_REFRESH_SEC, "NEO4J_DICT_LIMIT": NEO4J_DICT_LIMIT, "USE_OLLAMA_EMBED": USE_OLLAMA_EMBED, "USE_TENSORZERO_EMBED": USE_TENSORZERO_EMBED}
    }

@app.post("/hirag/admin/refresh")
def hirag_admin_refresh(_=Depends(require_admin_tailscale)):
    refresh_warm_dictionary()
    return {"ok": True, "entries": int(sum(len(s) for s in _warm_entities.values()))}

@app.post("/hirag/admin/cache/clear")
def hirag_admin_cache_clear(_=Depends(require_admin_tailscale)):
    _cache_entities.clear(); _cache_order.clear()
    return {"ok": True}

# ---------------- Geometry Bus minimal stub ----------------
@app.get("/shape/point/{point_id}/jump")
def shape_point_jump(point_id: str, _=Depends(require_tailscale)):
    if shape_store is None:
        raise HTTPException(503, "ShapeStore unavailable")
    loc = shape_store.jump_locator(point_id)
    if not loc:
        raise HTTPException(404, f"point '{point_id}' not found")
    return {"ok": True, "locator": loc}


@app.post("/geometry/event")
def geometry_event(body: Dict[str, Any], _=Depends(require_tailscale)):
    """Accept geometry.cgp.v1 events. Body example:
    {"type":"geometry.cgp.v1", "data": { ... CGP ... }}
    """
    if shape_store is None:
        raise HTTPException(503, "ShapeStore unavailable")
    try:
        payload = body.get("data") if isinstance(body, dict) else None
        if not isinstance(payload, dict):
            raise ValueError("missing data")
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
                try:
                    payload = decrypt_anchors(payload, CHIT_PASSPHRASE)
                except Exception as e:
                    raise HTTPException(400, f"anchor decrypt failed: {e}")
        shape_store.on_geometry_event({"type": "geometry.cgp.v1", "data": payload})
        return {"ok": True}
    except Exception as e:
        logger.exception("geometry_event error")
        raise HTTPException(400, f"geometry event error: {e}")


@app.post("/geometry/decode/text")
def geometry_decode_text(body: Dict[str, Any], _=Depends(require_tailscale)):
    if not CHIT_DECODE_TEXT:
        raise HTTPException(501, "text decoder disabled")
    # mode: "learned" | "geometry"
    mode = (body.get("mode") or "geometry").lower()
    const_id = body.get("constellation_id")
    point_ids = body.get("point_ids") or []
    k = int(body.get("k", 5))
    if const_id:
        const = shape_store.get_constellation(const_id) if shape_store else None
        if not const:
            raise HTTPException(404, f"constellation '{const_id}' not found")
    else:
        const = None
    namespace = str(
        body.get("namespace")
        or (const.get("namespace") if isinstance(const, dict) and const.get("namespace") else NAMESPACE_DEFAULT)
    )
    if mode == "learned":
        # lazy import transformers
        try:
            from transformers import pipeline  # type: ignore
        except Exception:
            raise HTTPException(500, "transformers not installed; set CHIT_DECODE_TEXT=false or install extras")
        texts = []
        # pull codebook examples
        cb = _load_codebook(CHIT_CODEBOOK_PATH)
        for rec in cb[: min(64, len(cb))]:
            t = rec.get("text") or rec.get("summary")
            if t: texts.append(t)
        if const_id and const:
            s = const.get("summary")
            if s: texts.insert(0, s)
        if not texts:
            raise HTTPException(400, "no codebook or constellation text available")
        nlp = pipeline("summarization", model=os.environ.get("CHIT_T5_MODEL","t5-small"))
        out = nlp("\n".join(texts)[:4000], max_length=128, min_length=32, do_sample=False)
        summary = out[0].get("summary_text", "")
        summary, hrm_info = _hrm_controller.maybe_refine(summary, namespace=namespace)
        return {"mode": mode, "summary": summary, "used": len(texts), "hrm": hrm_info, "namespace": namespace}
    else:
        # geometry-only: return top-k point snippets ordered by confidence/proj
        pts = []
        if const_id and const:
            for p in const.get("points", []) or []:
                cid = p.get("id");
                if not cid: continue
                pts.append({
                    "id": cid,
                    "text": p.get("text"),
                    "proj": p.get("proj"),
                    "conf": p.get("conf"),
                })
        for pid in point_ids:
            sp = shape_store.get_point(str(pid)) if shape_store else None
            if sp:
                pts.append({"id": sp.id, "proj": sp.proj, "conf": sp.conf})
        pts.sort(key=lambda x: (x.get("conf") or 0.0, x.get("proj") or 0.0), reverse=True)
        hrm_info = _hrm_controller.status(namespace)
        return {"mode": mode, "points": pts[:k], "hrm": hrm_info, "namespace": namespace}


def _js_divergence(p: List[float], q: List[float]) -> float:
    import math
    def _kl(a, b):
        eps = 1e-9
        s = 0.0
        for i in range(min(len(a), len(b))):
            ai = max(a[i], eps); bi = max(b[i], eps)
            s += ai * math.log(ai/bi)
        return s
    m = [(pi + qi) * 0.5 for pi, qi in zip(p, q)]
    return 0.5 * (_kl(p, m) + _kl(q, m))


def _wasserstein_1d(p: List[float], q: List[float]) -> float:
    # discrete 1D: sum |CDF_p - CDF_q|
    import itertools
    from itertools import accumulate
    import math
    cdp = list(accumulate(p))
    cdq = list(accumulate(q))
    return sum(abs(a-b) for a, b in itertools.zip_longest(cdp, cdq, fillvalue=1.0)) / max(1, len(cdp))


@app.post("/geometry/calibration/report")
def geometry_calibration_report(body: Dict[str, Any], _=Depends(require_tailscale)):
    data = body.get("data")
    const_ids = body.get("constellation_ids") or []
    report = []
    consts = []
    if isinstance(data, dict):
        for sn in data.get("super_nodes", []) or []:
            consts.extend(sn.get("constellations", []) or [])
    for cid in const_ids:
        c = shape_store.get_constellation(cid) if shape_store else None
        if c: consts.append(c)
    if not consts:
        raise HTTPException(400, "no constellations provided")
    for c in consts:
        spec = c.get("spectrum") or []
        if not spec:
            report.append({"id": c.get("id"), "coverage": 0.0, "js": None, "w1": None}); continue
        s = [float(x) for x in spec]
        mass = sum(s) or 1.0
        s = [x/mass for x in s]
        # uniform baseline for now
        u = [1.0/len(s)]*len(s)
        js = _js_divergence(s, u)
        w1 = _wasserstein_1d(s, u)
        coverage = sum(1 for x in s if x > 0.01) / float(len(s))
        report.append({"id": c.get("id"), "coverage": coverage, "js": js, "w1": w1})
    return {"constellations": report}


@app.post("/geometry/decode/image")
def geometry_decode_image(body: Dict[str, Any], _=Depends(require_tailscale)):
    if not CHIT_DECODE_IMAGE:
        raise HTTPException(501, "image decoder disabled")
    try:
        from PIL import Image  # type: ignore
        import numpy as np  # type: ignore
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
        model = _get_clip_model()
        text_emb = model.encode([text], normalize_embeddings=True, convert_to_numpy=True)
        img_list = []
        for url in images:
            try:
                r = _fetch_remote_image(url)
            except (urllib3.exceptions.HTTPError, OSError) as e:
                raise HTTPException(502, f"failed to fetch image: {e}")
            image_bytes = r.data
            if not image_bytes:
                raise HTTPException(400, f"remote image returned empty body for {url}")
            try:
                img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            except Exception as e:
                raise HTTPException(400, f"invalid image payload for {url}: {e}")
            img_list.append(img)
        img_embs = model.encode(img_list, normalize_embeddings=True, convert_to_numpy=True)
        sims = (img_embs @ text_emb.T).squeeze()
        ranked = sorted(zip(images, np.asarray(sims).tolist()), key=lambda x: x[1], reverse=True)
        return {"ranked": [{"url": u, "score": float(s)} for u, s in ranked]}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("image decode error")
        raise HTTPException(500, f"image decode error: {e}")


@app.post("/geometry/decode/audio")
def geometry_decode_audio(body: Dict[str, Any], _=Depends(require_tailscale)):
    if not CHIT_DECODE_AUDIO:
        raise HTTPException(501, "audio decoder disabled")
    try:
        import numpy as np  # type: ignore
    except Exception:
        raise HTTPException(500, "missing numpy dependency for audio decode")
    const_id = body.get("constellation_id")
    audios = body.get("audios") or []
    if not audios:
        raise HTTPException(400, "audios list required")
    const = shape_store.get_constellation(const_id) if (shape_store and const_id) else None
    text = body.get("text") or (const.get("summary") if const else None)
    if not text:
        raise HTTPException(400, "text or constellation summary required for anchor")
    try:
        model = _get_clap_model()
        audio_embs = model.get_audio_embedding_from_filelist(x=audios, use_tensor=False)
        text_emb = model.get_text_embedding([text], use_tensor=False)
        a = np.asarray(audio_embs, dtype=float)
        t = np.asarray(text_emb, dtype=float).reshape(1, -1)
        a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
        t = t / (np.linalg.norm(t, axis=1, keepdims=True) + 1e-9)
        sims = (a @ t.T).squeeze()
        ranked = sorted(zip(audios, np.asarray(sims).tolist()), key=lambda x: x[1], reverse=True)
        return {"ranked": [{"path": u, "score": float(s)} for u, s in ranked]}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("audio decode error")
        raise HTTPException(500, f"audio decode error: {e}")

@app.get("/")
def index(_=Depends(require_tailscale)):
    return {"ok": True, "hint": "POST /hirag/query"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT)
