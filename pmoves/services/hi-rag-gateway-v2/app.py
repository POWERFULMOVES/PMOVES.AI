"""PMOVES Hi-RAG Gateway v2 - slim wiring module.

All business logic lives in dedicated modules:
  config, models, embeddings, rerank, security, geometry_bus,
  clients/{qdrant,neo4j,openai_compat}, routes/{health,query,geometry,models}.
"""

import sys
from pathlib import Path

# Ensure service directory on sys.path for sibling module imports
try:
    _service_dir = Path(__file__).resolve().parent
    if str(_service_dir) not in sys.path:
        sys.path.insert(0, str(_service_dir))
except Exception:
    pass

# Ensure repo root on sys.path for shared tools (services.common, libs.*, etc.)
try:
    _repo_root = Path(__file__).resolve().parents[2]
    if str(_repo_root) not in sys.path:
        sys.path.append(str(_repo_root))
except Exception:
    pass

from fastapi import FastAPI, Request, HTTPException  # noqa: F401
from fastapi.staticfiles import StaticFiles

from geometry_bus import lifespan

# ── FastAPI application ──────────────────────────────────────────────────────
app = FastAPI(
    title="PMOVES Hi-RAG Gateway v2 (hybrid + rerank)",
    version="2.1.0",
    lifespan=lifespan,
)

# ── Route modules ───────────────────────────────────────────────────────────
from routes.health import router as _health_router
from routes.query import router as _query_router
from routes.geometry import router as _geometry_router
from routes.models import router as _models_router

app.include_router(_health_router)
app.include_router(_query_router)
app.include_router(_geometry_router)
app.include_router(_models_router)

# ── Static geometry UI ──────────────────────────────────────────────────────
app.mount(
    "/geometry",
    StaticFiles(directory=str(Path(__file__).resolve().parent / "web"), html=True),
    name="geometry",
)

# ── Backward-compatible re-exports (tests import these from app) ────────────
from config import (  # noqa: E402, F401
    RERANK_ENABLE, RERANK_MODEL, RERANK_PROVIDER, RERANK_TOPN, RERANK_K,
    RERANK_FUSION, USE_MEILI, GRAPH_BOOST, ALPHA, COLL, MEILI_URL,
    MEILI_API_KEY, NAMESPACE_DEFAULT, QUERY_NAMESPACE_DEFAULT,
    CHIT_REQUIRE_SIGNATURE, CHIT_PASSPHRASE, CHIT_DECRYPT_ANCHORS,
    CHIT_PERSIST_DB, CHIT_DECODE_TEXT, CHIT_DECODE_IMAGE, CHIT_DECODE_AUDIO,
    CHIT_CODEBOOK_PATH, CHIT_T5_MODEL, CHIT_CLIP_MODEL,
    PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE,
    GAN_SIDECAR_ENABLED, NATS_URL, DEVICE, MODEL, QDRANT_URL,
    logger, _reranker, _rerank_model_label, _embedder,
    get_rerank_status, _CUDA_AVAILABLE, _RERANK_FP16_EFFECTIVE,
    RERANK_MODEL_RESOLVED, RERANK_MODEL_PATH, RERANK_USE_FP16_OVERRIDE,
    TAILSCALE_ONLY, TAILSCALE_ADMIN_ONLY, TAILSCALE_CIDRS,
    SUPABASE_REST_URL, SUPABASE_SERVICE_KEY, SUPABASE_ANON_KEY,
    HRM_ENABLED, HRM_FAST_THRESHOLD, HRM_MAX_PONDER_STEPS, HRM_HALT_THRESHOLD,
    EMBEDDING_MODEL, EMBEDDING_MODEL_TYPE, EMBEDDING_DIMENSION,
    RERANKER_TYPE, _embedding_model_loaded, _reranker_model_loaded,
)
from models import QueryReq, QueryResp, UpsertReq, UpsertItem  # noqa: F401
from embeddings import embed_query  # noqa: F401
from embeddings import (  # noqa: F401
    swap_embedding_model, get_embedding_status, get_embedding_dimension,
    embed_query_multi,
)
from rerank import hybrid_score, _get_reranker  # noqa: F401
from rerank import (  # noqa: F401
    swap_reranker_model, get_reranker_status, compute_rerank_scores,
)
from security import (  # noqa: F401
    require_tailscale, require_admin_tailscale,
    _client_ip, _tailscale_ip_allowed, _tailscale_violation_detail,
    _fetch_remote_image, _enrich_mindmap_item,
)
from geometry_bus import (  # noqa: F401
    shape_store, _hrm_controller, _enhanced_hrm,
    _room_add, _room_remove, _room_broadcast, _room_broadcast_roster,
    _room_ws_id, _room_ids,
    _geometry_context, _get_active_builder_pack,
    _load_codebook, _get_gan_sidecar, _persist_cgp_to_db,
    # additional re-exports for test backward-compat
    geometry_params, _active_builder_packs,
    _set_active_builder_pack, _fetch_geometry_pack, _apply_swarm_meta,
)
try:  # noqa: F401
    from services.common.shape_store import ShapeStore  # noqa: F401
except Exception:
    ShapeStore = None  # type: ignore[misc]
from routes.health import admin_rerank_status, admin_hrm_status  # noqa: F401
from routes.geometry import geometry_decode_text, mindmap_route  # noqa: F401
from clients.qdrant import qdrant, _qdrant_search, ensure_qdrant_collection  # noqa: F401
from clients.neo4j import driver, _warm_entities, _warm_last, graph_terms  # noqa: F401
from clients.openai_compat import meili_lexical, _extract_persona  # noqa: F401
