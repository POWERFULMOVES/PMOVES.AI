"""Pydantic request / response models for hi-rag-gateway-v2."""

from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

from config import ALPHA, QUERY_NAMESPACE_DEFAULT, NAMESPACE_DEFAULT


class QueryReq(BaseModel):
    query: str
    namespace: str = Field(default=QUERY_NAMESPACE_DEFAULT)
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


class ProvenanceAcceptedItem(BaseModel):
    content_id: str
    text: str
    source_ref: str
    shape_id: str
    merkle_root: str
    graphiti_mark: str
    kb_namespace: str = Field(default=NAMESPACE_DEFAULT)
    accepted_reason: Optional[str] = None
    provenance_refs: Optional[List[str]] = None
    favorite_words: Optional[List[str]] = None
    anchor_terms: Optional[List[str]] = None
    semantic_weights: Optional[List[Dict[str, Any]]] = None
    scorecard: Dict[str, Any] = {}
    meta: Optional[Dict[str, Any]] = None


class ProvenanceUpsertReq(BaseModel):
    items: List[ProvenanceAcceptedItem]
    ensure_collection: bool = True
    index_lexical: bool = True
