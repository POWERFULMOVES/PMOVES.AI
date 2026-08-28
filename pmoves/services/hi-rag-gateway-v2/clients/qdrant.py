"""Qdrant vector database client and search helpers."""

import os
from typing import List, Optional

from fastapi import HTTPException
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Filter, FieldCondition, MatchValue, Distance, VectorParams, PointStruct
    try:
        from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
    except ImportError:
        ResponseHandlingException = None  # type: ignore
        UnexpectedResponse = None  # type: ignore
except ImportError:
    QdrantClient = None  # type: ignore
    Filter = None  # type: ignore
    FieldCondition = None  # type: ignore
    MatchValue = None  # type: ignore
    Distance = None  # type: ignore
    VectorParams = None  # type: ignore
    PointStruct = None  # type: ignore
    ResponseHandlingException = None  # type: ignore
    UnexpectedResponse = None  # type: ignore

from config import QDRANT_URL, QDRANT__API_KEY, COLL, RECREATE_ON_MISMATCH, logger

# Safety threshold: refuse to auto-recreate collections with more points than
# this unless QDRANT_FORCE_RECREATE=true.  Prevents accidental data loss when
# an embedding model change causes a dimension mismatch on a populated index.
_RECREATE_POINT_THRESHOLD = int(os.environ.get("QDRANT_RECREATE_POINT_THRESHOLD", "0"))
_FORCE_RECREATE = os.environ.get("QDRANT_FORCE_RECREATE", "false").lower() in (
    "true", "1", "yes",
)

# --- Qdrant client instance ---
if QdrantClient is not None:
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT__API_KEY or None, timeout=30.0)
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


def _collection_point_count(collection_name: str) -> int:
    """Return the number of indexed points in a Qdrant collection.

    Returns 0 when the count cannot be determined (missing API, network
    error, etc.) so callers can still proceed safely.
    """
    try:
        info = qdrant.get_collection(collection_name)
        count = getattr(info, "points_count", None)
        if count is None:
            # Some client versions nest this under vectors_count or status.
            count = getattr(info, "vectors_count", 0)
        return int(count) if count else 0
    except Exception:
        return 0


def _is_collection_missing_error(exc: Exception) -> bool:
    """Return True when the Qdrant client is specifically reporting 404/missing."""
    status_code = getattr(exc, "status_code", None)
    if status_code == 404:
        return True

    qdrant_error_types = tuple(
        err_type
        for err_type in (UnexpectedResponse, ResponseHandlingException)
        if err_type is not None
    )
    if qdrant_error_types and isinstance(exc, qdrant_error_types):
        message = str(exc).lower()
        return "not found" in message and "collection" in message

    return False


def ensure_qdrant_collection(vector_dim: int):
    """Create or resync the Qdrant collection when the embed dimension changes.

    Safety hierarchy (strictest to most permissive):
    1. ``QDRANT_RECREATE_ON_DIM_MISMATCH=false`` (default) -- HTTP 409 on
       mismatch; never drops data.
    2. ``QDRANT_RECREATE_ON_DIM_MISMATCH=true`` -- permits recreation only
       when the collection is empty *or* the point count is at or below
       ``QDRANT_RECREATE_POINT_THRESHOLD`` (default 0).
    3. ``QDRANT_FORCE_RECREATE=true`` -- overrides the point-count guard;
       always recreates.  Intended for one-shot migration commands, never
       for production runtime.
    """
    try:
        info = qdrant.get_collection(COLL)
    except Exception as exc:
        if _is_collection_missing_error(exc):
            info = None
        else:
            raise

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

            # --- Data-loss safety guard ---
            point_count = _collection_point_count(COLL)
            if point_count > _RECREATE_POINT_THRESHOLD and not _FORCE_RECREATE:
                logger.error(
                    "Qdrant collection %s has %d points but dimension changed "
                    "(%s -> %s). Refusing to auto-recreate to prevent data loss. "
                    "Set QDRANT_FORCE_RECREATE=true to override.",
                    COLL, point_count, current_dim, vector_dim,
                )
                raise HTTPException(
                    409,
                    f"Qdrant dimension mismatch: collection has {current_dim}d, "
                    f"embedding returned {vector_dim}d. Collection contains "
                    f"{point_count} points — refusing to auto-recreate to prevent "
                    f"data loss (set QDRANT_FORCE_RECREATE=true to override)."
                )

            logger.warning(
                "Qdrant collection %s dimension changed (%s -> %s, %d points); "
                "recreating (DATA LOSS)",
                COLL,
                current_dim,
                vector_dim,
                point_count,
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
        raise HTTPException(500, f"Qdrant collection error: {e}") from e
