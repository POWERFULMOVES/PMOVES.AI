"""Qdrant vector database client and search helpers."""

from typing import List, Optional

from fastapi import HTTPException
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Filter, FieldCondition, MatchValue, Distance, VectorParams, PointStruct
except ImportError:
    QdrantClient = None  # type: ignore
    Filter = None  # type: ignore
    FieldCondition = None  # type: ignore
    MatchValue = None  # type: ignore
    Distance = None  # type: ignore
    VectorParams = None  # type: ignore
    PointStruct = None  # type: ignore

from config import QDRANT_URL, COLL, RECREATE_ON_MISMATCH, logger

# --- Qdrant client instance ---
if QdrantClient is not None:
    qdrant = QdrantClient(url=QDRANT_URL, timeout=30.0)
else:
    qdrant = None  # type: ignore


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
        try:
            return qdrant.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=with_payload,
                with_vectors=with_vectors,
            )
        except AttributeError:
            # Some client builds expose the symbol but fail at runtime.
            pass

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
            # Older signatures may still use `vector=...`.
            resp = qdrant.query_points(vector=query_vector, **kwargs)
        except AttributeError:
            resp = None
        if resp is None:
            pass
        elif isinstance(resp, list):
            return resp
        else:
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
        try:
            resp = qdrant.search_points(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=with_payload,
                with_vectors=with_vectors,
            )
        except AttributeError:
            resp = None
        if resp is None:
            raise AttributeError("qdrant client has no compatible search/query API")
        if isinstance(resp, list):
            return resp
        result = getattr(resp, "result", None)
        if isinstance(result, list):
            return result
        return []

    raise AttributeError("qdrant client has no compatible search/query API")


def ensure_qdrant_collection(vector_dim: int):
    """Create or resync the Qdrant collection when the embed dimension changes.

    When QDRANT_RECREATE_ON_DIM_MISMATCH=false (default), a dimension mismatch
    returns HTTP 409 instead of silently destroying indexed vectors.
    """
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
            if not RECREATE_ON_MISMATCH:
                logger.error(
                    "Qdrant collection %s dimension mismatch (%s stored vs %s requested). "
                    "Set QDRANT_RECREATE_ON_DIM_MISMATCH=true to auto-recreate (data loss!).",
                    COLL, current_dim, vector_dim,
                )
                raise HTTPException(
                    409,
                    f"Qdrant dimension mismatch: collection has {current_dim}d, "
                    f"embedding returned {vector_dim}d. Refusing to auto-recreate "
                    f"(QDRANT_RECREATE_ON_DIM_MISMATCH=false)."
                )
            logger.warning(
                "Qdrant collection %s dimension changed (%s -> %s); recreating (DATA LOSS)",
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ensure_qdrant_collection failed")
        raise HTTPException(500, f"Qdrant collection error: {e}")
