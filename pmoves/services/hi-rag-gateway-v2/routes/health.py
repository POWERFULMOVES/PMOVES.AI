"""Admin and health endpoints for hi-rag-gateway-v2."""

import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

import geometry_bus as _geometry_bus_mod
import clients.neo4j as _neo4j_mod
import config as _cfg
from security import require_admin_tailscale, require_tailscale

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
    model_report = _cfg._rerank_model_label or _cfg.RERANK_MODEL
    return {
        "rerank_enabled": _cfg.RERANK_ENABLE,
        "rerank_model": (model_report or None) if _cfg.RERANK_ENABLE else None,
        "rerank_loaded": _cfg._reranker is not None,
        "cuda": cuda,
        "use_meili": _cfg.USE_MEILI,
        "graph": {
            "boost": _cfg.GRAPH_BOOST,
            "types": len(_neo4j_mod._warm_entities),
            "last_refresh": _neo4j_mod._warm_last,
        },
        "alpha": _cfg.ALPHA,
        "collection": _cfg.COLL,
    }


@router.get("/hirag/admin/rerank-status")
def admin_rerank_status(request: Request):
    if os.environ.get("SMOKE_ALLOW_ADMIN_STATS", "false").lower() != "true":
        require_admin_tailscale(request)
    status = _cfg.get_rerank_status()
    status["model_report"] = _cfg._rerank_model_label or status["model"]
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
    _neo4j_mod.refresh_warm_dictionary()
    return {"ok": True, "last_refresh": _neo4j_mod._warm_last}


@router.post("/hirag/admin/cache/clear")
def hirag_admin_cache_clear(_=Depends(require_admin_tailscale)):
    _neo4j_mod.refresh_warm_dictionary()
    return {"ok": True}



@router.get("/hirag/admin/hrm-status")
def admin_hrm_status(request: Request):
    """Enhanced HRM dual-stream sidecar status."""
    if os.environ.get("SMOKE_ALLOW_ADMIN_STATS", "false").lower() != "true":
        require_admin_tailscale(request)
    legacy = (
        _geometry_bus_mod._hrm_controller.status("*")
        if _geometry_bus_mod._hrm_controller
        else {"enabled": False}
    )
    enhanced = (
        _geometry_bus_mod._enhanced_hrm.status()
        if _geometry_bus_mod._enhanced_hrm is not None
        else {"enabled": False, "loaded": False}
    )
    return {
        "legacy_hrm": legacy,
        "enhanced_hrm": enhanced,
        "config": {
            "HRM_ENABLED": _cfg.HRM_ENABLED,
            "HRM_FAST_THRESHOLD": _cfg.HRM_FAST_THRESHOLD,
            "HRM_MAX_PONDER_STEPS": _cfg.HRM_MAX_PONDER_STEPS,
            "HRM_HALT_THRESHOLD": _cfg.HRM_HALT_THRESHOLD,
        },
    }

@router.get("/")
def index(_=Depends(require_tailscale)):
    return {"ok": True, "service": "hi-rag-gateway-v2", "hint": "POST /hirag/query"}
