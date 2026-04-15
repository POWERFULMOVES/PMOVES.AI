"""Admin and health endpoints for hi-rag-gateway-v2."""

import os
from typing import Any, Dict

from fastapi import APIRouter, Request, Depends

from config import (
    RERANK_ENABLE, RERANK_MODEL, USE_MEILI, GRAPH_BOOST, ALPHA, COLL,
    logger, get_rerank_status, _rerank_model_label, _reranker,
)
from security import require_tailscale, require_admin_tailscale
from clients.neo4j import _warm_entities, _warm_last, refresh_warm_dictionary

router = APIRouter()


@router.get("/hirag/admin/stats")
def stats(request: Request):
    if os.environ.get("SMOKE_ALLOW_ADMIN_STATS", "false").lower() != "true":
        require_admin_tailscale(request)
    cuda = None
    try:
        import torch
        cuda = bool(torch.cuda.is_available())
    except Exception:
        cuda = None
    model_report = _rerank_model_label or RERANK_MODEL
    return {
        "rerank_enabled": RERANK_ENABLE,
        "rerank_model": (model_report or None) if RERANK_ENABLE else None,
        "rerank_loaded": _reranker is not None,
        "cuda": cuda,
        "use_meili": USE_MEILI,
        "graph": {"boost": GRAPH_BOOST, "types": len(_warm_entities), "last_refresh": _warm_last},
        "alpha": ALPHA,
        "collection": COLL,
    }


@router.get("/hirag/admin/rerank-status")
def admin_rerank_status(request: Request):
    if os.environ.get("SMOKE_ALLOW_ADMIN_STATS", "false").lower() != "true":
        require_admin_tailscale(request)
    status = get_rerank_status()
    status["model_report"] = _rerank_model_label or status["model"]
    return status


@router.post("/hirag/admin/reranker/model/label")
def set_rerank_model_label(body: Dict[str, Any], request: Request):
    if os.environ.get("SMOKE_ALLOW_ADMIN_STATS", "false").lower() != "true":
        require_admin_tailscale(request)
    import config as _cfg
    global _rerank_model_label_ref
    label = (body or {}).get("label") or ""
    _cfg._rerank_model_label = label.strip() or None
    return {"ok": True, "rerank_model_label": _cfg._rerank_model_label}


@router.post("/hirag/admin/refresh")
def hirag_admin_refresh(_=Depends(require_admin_tailscale)):
    refresh_warm_dictionary()
    return {"ok": True, "last_refresh": _warm_last}


@router.post("/hirag/admin/cache/clear")
def hirag_admin_cache_clear(_=Depends(require_admin_tailscale)):
    refresh_warm_dictionary()
    return {"ok": True}


@router.get("/")
def index(_=Depends(require_tailscale)):
    return {"ok": True, "service": "hi-rag-gateway-v2", "hint": "POST /hirag/query"}
