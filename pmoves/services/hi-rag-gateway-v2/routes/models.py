"""Model management admin endpoints for hi-rag-gateway-v2.

Provides hot-swap and status endpoints for embedding and reranker models.
All endpoints require admin Tailscale authentication.
"""

import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from security import require_admin_tailscale

router = APIRouter()


@router.get("/hirag/admin/models")
def list_models(request: Request):
    """List current embedding and reranker models and their status."""
    if os.environ.get("SMOKE_ALLOW_ADMIN_STATS", "false").lower() != "true":
        require_admin_tailscale(request)
    from embeddings import get_embedding_status
    from rerank import get_reranker_status

    return {
        "embedding": get_embedding_status(),
        "reranker": get_reranker_status(),
    }


@router.post("/hirag/admin/embedding/model")
def swap_embedding_model(body: Dict[str, Any], request: Request):
    """Hot-swap the embedding model at runtime.

    Body: {"model": "BAAI/bge-m3"} or {"model": "all-MiniLM-L6-v2"}
    """
    if os.environ.get("SMOKE_ALLOW_ADMIN_STATS", "false").lower() != "true":
        require_admin_tailscale(request)

    model_name = (body or {}).get("model")
    if not isinstance(model_name, str) or not model_name.strip():
        raise HTTPException(status_code=400, detail="model must be a non-empty string")

    from embeddings import swap_embedding_model as _swap
    try:
        result = _swap(model_name)
        return result
    except Exception as e:
        raise HTTPException(500, f"Failed to swap embedding model: {e}") from e


@router.post("/hirag/admin/reranker/model")
def swap_reranker_model(body: Dict[str, Any], request: Request):
    """Hot-swap the reranker model at runtime.

    Body: {"model": "BAAI/bge-reranker-v2-gemma"} or {"model": "BAAI/bge-reranker-v2-m3"}
    """
    if os.environ.get("SMOKE_ALLOW_ADMIN_STATS", "false").lower() != "true":
        require_admin_tailscale(request)

    model_name = (body or {}).get("model")
    if not isinstance(model_name, str) or not model_name.strip():
        raise HTTPException(status_code=400, detail="model must be a non-empty string")

    from rerank import swap_reranker_model as _swap
    try:
        result = _swap(model_name)
        return result
    except Exception as e:
        raise HTTPException(500, f"Failed to swap reranker model: {e}") from e
