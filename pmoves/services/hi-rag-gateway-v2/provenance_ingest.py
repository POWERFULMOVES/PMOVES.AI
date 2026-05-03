"""Helpers for ingesting provenance-accepted content into Hi-RAG v2."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

import requests

from clients.qdrant import PointStruct, ensure_qdrant_collection, qdrant
from config import COLL, MEILI_API_KEY, MEILI_URL, NAMESPACE_DEFAULT, logger
from embeddings import embed_query


def _compact(value: Any) -> Any:
    """
    Recursively remove empty or null-like values from a nested structure.
    
    Parameters:
    	value (Any): A value to compact; may be a dict, list, or any scalar. Dicts and lists are processed recursively and have entries/elements removed when they are empty, `None`, `""`, `[]`, or `{}`.
    
    Returns:
    	compacted (Any or None): The cleaned value with empty entries removed; returns `None` if the input or resulting structure is empty.
    """
    if isinstance(value, dict):
        cleaned = {
            key: compacted
            for key, item in value.items()
            if (compacted := _compact(item)) is not None
        }
        return cleaned or None
    if isinstance(value, list):
        cleaned_list = [item for item in (_compact(v) for v in value) if item is not None]
        return cleaned_list or None
    if value in (None, "", [], {}):
        return None
    return value


def provenance_payload_to_upsert_item(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a provenance-accepted payload into a standardized upsert item suitable for embedding and Qdrant/Meilisearch storage.
    
    Parameters:
        payload (Dict[str, Any]): Incoming provenance-accepted payload. Expected keys that may be used include
            `content_id`, `shape_id`, `kb_namespace` or `namespace`, `chunk_id`, `doc_id`, `text`, `meta`, and
            provenance metadata fields such as `source_ref`, `merkle_root`, `graphiti_mark`, `accepted_reason`,
            `provenance_refs`, `favorite_words`, `anchor_terms`, `semantic_weights`, and `scorecard`.
    
    Returns:
        Dict[str, Any]: An item dictionary with keys:
            - `doc_id` (str): Derived document identifier.
            - `chunk_id` (str): Derived chunk identifier.
            - `text` (str): Text content (defaults to empty string if missing).
            - `namespace` (str): Resolved namespace (defaults to module default).
            - `payload` (Dict[str, Any]): Compacted provenance payload with empty values removed; defaults to an empty dict.
    """
    content_id = str(payload.get("content_id") or payload.get("shape_id") or "").strip()
    shape_id = str(payload.get("shape_id") or content_id).strip()
    namespace = str(payload.get("kb_namespace") or payload.get("namespace") or NAMESPACE_DEFAULT).strip() or NAMESPACE_DEFAULT
    chunk_id = str(payload.get("chunk_id") or shape_id or content_id).strip()
    doc_id = str(payload.get("doc_id") or f"provenance:{content_id or chunk_id}").strip()

    item = {
        "doc_id": doc_id,
        "chunk_id": chunk_id,
        "text": str(payload.get("text") or ""),
        "namespace": namespace,
        "payload": _compact(
            {
                "content_id": content_id,
                "shape_id": shape_id,
                "source_ref": payload.get("source_ref"),
                "merkle_root": payload.get("merkle_root"),
                "graphiti_mark": payload.get("graphiti_mark"),
                "accepted_reason": payload.get("accepted_reason"),
                "provenance_refs": payload.get("provenance_refs"),
                "favorite_words": payload.get("favorite_words"),
                "anchor_terms": payload.get("anchor_terms"),
                "semantic_weights": payload.get("semantic_weights"),
                "scorecard": payload.get("scorecard"),
                "source_topic": "content.hirag.accepted.v1",
                "meta": payload.get("meta"),
            }
        )
        or {},
    }
    return item


def _index_lexical_docs(items: List[Dict[str, Any]]) -> int:
    """
    Ensure a Meilisearch index exists and publish the provided items as documents to that index.
    
    Each item should be a dict with keys used to build the document: `chunk_id`, `doc_id`, `text`, optional `namespace`, and optional `payload` (a dict of extra fields). The function attempts to create the index (id `COLL`) and then POSTs the assembled documents to Meilisearch.
    
    Parameters:
        items (List[Dict[str, Any]]): List of item dictionaries to index.
    
    Returns:
        int: The number of documents sent if Meilisearch responded with an OK status, `0` otherwise.
    """
    headers = {"Content-Type": "application/json"}
    if MEILI_API_KEY:
        headers["Authorization"] = f"Bearer {MEILI_API_KEY}"

    requests.post(
        f"{MEILI_URL}/indexes",
        headers=headers,
        data=json.dumps({"uid": COLL}),
        timeout=5,
    )
    docs = []
    for item in items:
        docs.append(
            {
                "id": item.get("chunk_id"),
                "chunk_id": item.get("chunk_id"),
                "doc_id": item.get("doc_id"),
                "text": item.get("text"),
                "namespace": item.get("namespace", NAMESPACE_DEFAULT),
                **(item.get("payload") or {}),
            }
        )
    if not docs:
        return 0

    response = requests.post(
        f"{MEILI_URL}/indexes/{COLL}/documents",
        headers=headers,
        data=json.dumps(docs),
        timeout=30,
    )
    return len(docs) if response.ok else 0


def upsert_provenance_payloads(
    payloads: List[Dict[str, Any]],
    *,
    ensure_collection: bool = True,
    index_lexical: bool = True,
) -> Dict[str, Any]:
    """
    Convert and upsert provenance-accepted payloads into the vector store and optionally index their text lexically.
    
    Processes the given list of payload dictionaries by filtering ones that contain text, normalizing each into an upsertable item, embedding their text, creating deterministic Qdrant point IDs, and upserting the resulting points into the configured Qdrant collection. Optionally ensures the Qdrant collection vector size and adds documents to Meilisearch for lexical search; Meilisearch failures are caught and logged without aborting the upsert.
    
    Parameters:
        payloads (List[Dict[str, Any]]): Iterable of provenance payload dictionaries; only entries with a truthy `"text"` field are processed.
        ensure_collection (bool, optional): If true and embeddings are produced, ensure the Qdrant collection exists and matches the embedding dimensionality. Defaults to True.
        index_lexical (bool, optional): If true, attempt to index items into Meilisearch for lexical search; failures are logged and do not fail the overall operation. Defaults to True.
    
    Returns:
        Dict[str, Any]: Result summary containing:
            - `ok` (bool): Always `True` on successful completion.
            - `upserted` (int): Number of points upserted into Qdrant.
            - `lexical_indexed` (int): Number of documents indexed into Meilisearch (0 on failure or if disabled).
            - `items` (List[Dict[str, Any]]): The normalized items that were prepared for upsert.
    
    Raises:
        RuntimeError: If the Qdrant client or PointStruct type is unavailable.
    """
    accepted_payloads = [payload for payload in payloads if isinstance(payload, dict) and payload.get("text")]
    if not accepted_payloads:
        return {"ok": True, "upserted": 0, "lexical_indexed": 0}

    items = [provenance_payload_to_upsert_item(payload) for payload in accepted_payloads]
    vectors = [embed_query(item.get("text", "")) for item in items]

    if ensure_collection and vectors:
        ensure_qdrant_collection(len(vectors[0]))

    if PointStruct is None or qdrant is None:
        raise RuntimeError("Qdrant client unavailable for provenance ingest")

    points = []
    for item, vector in zip(items, vectors):
        chunk_id = str(item.get("chunk_id") or item.get("doc_id"))
        qdrant_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))
        payload = {
            "doc_id": item.get("doc_id"),
            "chunk_id": chunk_id,
            "text": item.get("text"),
            "namespace": item.get("namespace", NAMESPACE_DEFAULT),
        }
        extra = item.get("payload") or {}
        if isinstance(extra, dict):
            for key, value in extra.items():
                payload.setdefault(key, value)
        points.append(PointStruct(id=qdrant_id, vector=vector, payload=payload))

    if points:
        qdrant.upsert(collection_name=COLL, points=points)

    lexical_indexed = 0
    if index_lexical and items:
        try:
            lexical_indexed = _index_lexical_docs(items)
        except Exception:
            logger.exception("Meili lexical indexing failed for provenance ingest")

    return {
        "ok": True,
        "upserted": len(points),
        "lexical_indexed": lexical_indexed,
        "items": items,
    }
