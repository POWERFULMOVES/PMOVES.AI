"""Provenance-aware upsert routes for hi-rag-gateway-v2."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from models import ProvenanceUpsertReq
from provenance_ingest import upsert_provenance_payloads
from security import require_admin_tailscale

router = APIRouter()


@router.post("/hirag/upsert-provenance")
def hirag_upsert_provenance(
    req: ProvenanceUpsertReq = Body(...),
    _=Depends(require_admin_tailscale),
):
    """
    Accept a ProvenanceUpsertReq and upsert its serialized items into the provenance store.
    
    Parameters:
        req (ProvenanceUpsertReq): Request containing `items` to upsert and the flags `ensure_collection` and `index_lexical` that control collection creation and lexical indexing.
    
    Returns:
        The value returned by `upsert_provenance_payloads`, containing the upsert operation's outcomes and related metadata.
    """
    payloads = [item.model_dump() for item in req.items]
    return upsert_provenance_payloads(
        payloads,
        ensure_collection=req.ensure_collection,
        index_lexical=req.index_lexical,
    )
