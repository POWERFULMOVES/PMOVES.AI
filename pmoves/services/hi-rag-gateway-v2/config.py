"""Central configuration for hi-rag-gateway-v2.

All environment variables, parse helpers, logging setup, and global state.
Heavy dependencies (torch, qdrant_client, etc.) are wrapped in try/except ImportError.
"""

import os
import time
import math
import json
import logging
import re
import sys
import copy
import threading
import socket
import ipaddress
from pathlib import Path
from typing import List, Optional, Dict, Any

# --- Optional heavy dependencies (graceful degradation) ---
try:
    import torch
except ImportError:
    torch = None  # type: ignore

try:
    from qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None  # type: ignore

try:
    from FlagEmbedding import FlagReranker
except ImportError:
    FlagReranker = None  # type: ignore

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None  # type: ignore

import requests
import urllib3
from urllib.parse import quote_plus, urlparse

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
COLL = os.environ.get("QDRANT_COLLECTION", "pmoves_chunks_qwen3")
MODEL = os.environ.get("SENTENCE_MODEL", "all-MiniLM-L6-v2")
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
        _RERANK_CONFIG_WARNINGS.append(
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

# --- Device detection ---
_USE_CUDA_ENV = os.environ.get("USE_CUDA", "true").lower() == "true"
_CUDA_AVAILABLE = torch.cuda.is_available() if torch else False
DEVICE = "cuda" if _USE_CUDA_ENV and _CUDA_AVAILABLE else "cpu"
_RERANK_FP16_EFFECTIVE = (
    RERANK_USE_FP16_OVERRIDE if RERANK_USE_FP16_OVERRIDE is not None else DEVICE == "cuda"
)


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

USE_MEILI = os.environ.get("USE_MEILI", "false").lower() == "true"
MEILI_URL = os.environ.get("MEILI_URL", "http://meilisearch:7700")
MEILI_API_KEY = os.environ.get("MEILI_API_KEY", "master_key")

_RERANK_STATUS_CACHE = get_rerank_status()

# --- Provider embedding fallback ---
try:
    from libs.providers.embedding import embed_text as _embed_via_providers
except ImportError:
    _embed_via_providers = None  # type: ignore

GRAPH_BOOST = float(os.environ.get("GRAPH_BOOST", "0.15"))
NEO4J_URL = (os.environ.get("NEO4J_URL", "bolt://neo4j:7687") or "").strip()
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "neo4j")
NEO4J_DICT_REFRESH_SEC = int(os.environ.get("NEO4J_DICT_REFRESH_SEC", "60"))
NEO4J_DICT_LIMIT = int(os.environ.get("NEO4J_DICT_LIMIT", "50000"))
ENTITY_CACHE_TTL = int(os.environ.get("ENTITY_CACHE_TTL", "60"))
ENTITY_CACHE_MAX = int(os.environ.get("ENTITY_CACHE_MAX", "1000"))

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
_jwt_service_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
_explicit_realtime_key = os.environ.get("SUPABASE_REALTIME_KEY") or os.environ.get("REALTIME_ANON_KEY")


def _is_jwt(key: str) -> bool:
    return bool(key and key.startswith("eyJ") and key.count(".") == 2)


SUPABASE_REALTIME_KEY = (
    _jwt_service_key if _is_jwt(_jwt_service_key) else
    _explicit_realtime_key if _is_jwt(_explicit_realtime_key) else
    SUPABASE_ANON_KEY if _is_jwt(SUPABASE_ANON_KEY) else
    _jwt_service_key or _explicit_realtime_key or SUPABASE_ANON_KEY
)
GEOMETRY_CACHE_WARM_LIMIT = int(os.environ.get("GEOMETRY_CACHE_WARM_LIMIT", "64"))
# Realtime connection retry configuration
GEOMETRY_REALTIME_BACKOFF = float(os.environ.get("GEOMETRY_REALTIME_BACKOFF", "5.0"))
GEOMETRY_REALTIME_MAX_BACKOFF = float(os.environ.get("GEOMETRY_REALTIME_MAX_BACKOFF", "60.0"))
GEOMETRY_REALTIME_STARTUP_GRACE = float(os.environ.get("GEOMETRY_REALTIME_STARTUP_GRACE", "120.0"))

TAILSCALE_ONLY = os.environ.get("TAILSCALE_ONLY", "false").lower() == "true"
TAILSCALE_ADMIN_ONLY = os.environ.get("TAILSCALE_ADMIN_ONLY", "false").lower() == "true"
TAILSCALE_CIDRS = [c.strip() for c in os.environ.get("TAILSCALE_CIDRS", "100.64.0.0/10").split(",") if c.strip()]
TRUSTED_PROXY_SOURCES = [c.strip() for c in os.environ.get("HIRAG_TRUSTED_PROXIES", "").split(",") if c.strip()]

HTTP_PORT = int(os.environ.get("HIRAG_HTTP_PORT", "8086"))
NAMESPACE_DEFAULT = os.environ.get("INDEXER_NAMESPACE", "pmoves")
QUERY_NAMESPACE_DEFAULT = os.environ.get("QUERY_NAMESPACE", "*")

# --- CHIT / Geometry env vars ---
CHIT_REQUIRE_SIGNATURE = os.environ.get("CHIT_REQUIRE_SIGNATURE", "false").lower() == "true"
CHIT_PASSPHRASE = os.environ.get("CHIT_PASSPHRASE", "")
CHIT_DECRYPT_ANCHORS = os.environ.get("CHIT_DECRYPT_ANCHORS", "false").lower() == "true"
CHIT_DECODE_TEXT = os.environ.get("CHIT_DECODE_TEXT", "false").lower() == "true"
CHIT_DECODE_IMAGE = os.environ.get("CHIT_DECODE_IMAGE", "false").lower() == "true"
CHIT_DECODE_AUDIO = os.environ.get("CHIT_DECODE_AUDIO", "false").lower() == "true"
CHIT_CODEBOOK_PATH = os.environ.get("CHIT_CODEBOOK_PATH", "datasets/structured_dataset.jsonl")
CHIT_T5_MODEL = os.environ.get("CHIT_T5_MODEL", "t5-small")
CHIT_CLIP_MODEL = os.environ.get("CHIT_CLIP_MODEL", "clip-ViT-B-32")
CHIT_IMAGE_FETCH_ALLOW_PRIVATE = os.environ.get("CHIT_IMAGE_FETCH_ALLOW_PRIVATE", "false").lower() == "true"
CHIT_IMAGE_FETCH_ALLOWED_HOSTS = {
    host.strip().lower()
    for host in os.environ.get("CHIT_IMAGE_FETCH_ALLOWED_HOSTS", "").split(",")
    if host.strip()
}
CHIT_PERSIST_DB = os.environ.get("CHIT_PERSIST_DB", "false").lower() == "true"
GAN_SIDECAR_ENABLED = os.environ.get("GAN_SIDECAR_ENABLED", "false").lower() == "true"

# --- Enhanced HRM dual-stream configuration (P6 Phase 3) ---
HRM_ENABLED = os.environ.get("HRM_ENABLED", "false").lower() == "true"
HRM_FAST_THRESHOLD = float(os.environ.get("HRM_FAST_THRESHOLD", "0.3"))
HRM_MAX_PONDER_STEPS = int(os.environ.get("HRM_MAX_PONDER_STEPS", "8"))
HRM_HALT_THRESHOLD = float(os.environ.get("HRM_HALT_THRESHOLD", "0.9"))

PGHOST = os.environ.get("PGHOST")
PGPORT = int(os.environ.get("PGPORT", "5432"))
PGUSER = os.environ.get("PGUSER")
PGPASSWORD = os.environ.get("PGPASSWORD")
PGDATABASE = os.environ.get("PGDATABASE")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_embedder = None

RECREATE_ON_MISMATCH = os.environ.get(
    "QDRANT_RECREATE_ON_DIM_MISMATCH", "false"
).lower() in ("true", "1", "yes")
