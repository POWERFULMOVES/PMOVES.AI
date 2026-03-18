"""
Lightweight model-registry client for PMOVES services.

Queries the model-registry service (port 8110) for model configuration
instead of relying on hardcoded env-var defaults. Falls back gracefully
if the registry is unreachable.

Usage:
    from pmoves.libs.model_registry_client import get_model_for_service

    # Returns model_id string or None
    embed_model = get_model_for_service("hi-rag", "embedding")
    rerank_model = get_model_for_service("hi-rag", "reranker")

Fallback chain: registry → env var → hardcoded default (caller decides).
"""

import os
import time
import logging
import threading
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL_REGISTRY_URL = os.environ.get(
    "MODEL_REGISTRY_URL", "http://model-registry:8110"
).rstrip("/")

# Cache TTL in seconds — don't hammer the registry on every embed call
CACHE_TTL = int(os.environ.get("MODEL_REGISTRY_CACHE_TTL", "300"))

_cache: Dict[str, dict] = {}
_cache_lock = threading.Lock()


def _cache_key(service: str, model_type: str) -> str:
    return f"{service}:{model_type}"


def _is_fresh(entry: dict) -> bool:
    return (time.monotonic() - entry.get("ts", 0)) < CACHE_TTL


def _query_registry(
    service: str, model_type: str, timeout: float = 5.0
) -> Optional[str]:
    """
    Query model-registry for the preferred model for a service+type.

    Tries service-specific mapping first, then falls back to global
    model list filtered by type.

    Returns the model_id string (e.g., "all-MiniLM-L6-v2") or None.
    """
    import requests  # lazy import — not all callers have requests

    # 1. Try service-specific mapping
    try:
        r = requests.get(
            f"{MODEL_REGISTRY_URL}/api/services/{service}/models",
            timeout=timeout,
        )
        if r.ok:
            items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
            for item in items:
                if item.get("model_type") == model_type and item.get("active", True):
                    model_id = item.get("model_id")
                    if model_id:
                        logger.info(
                            "model-registry: %s/%s → %s (service mapping)",
                            service, model_type, model_id,
                        )
                        return model_id
    except Exception as e:
        logger.debug("model-registry service query failed: %s", e)

    # 2. Fall back to global model list
    try:
        r = requests.get(
            f"{MODEL_REGISTRY_URL}/api/models",
            params={"model_type": model_type},
            timeout=timeout,
        )
        if r.ok:
            data = r.json()
            items = data.get("items", []) if isinstance(data, dict) else data
            for item in items:
                if item.get("active", True):
                    model_id = item.get("model_id")
                    if model_id:
                        logger.info(
                            "model-registry: %s/%s → %s (global)",
                            service, model_type, model_id,
                        )
                        return model_id
    except Exception as e:
        logger.debug("model-registry global query failed: %s", e)

    return None


def get_model_for_service(
    service: str, model_type: str, timeout: float = 5.0
) -> Optional[str]:
    """
    Get the preferred model_id for a service and model type.

    Cached with TTL. Thread-safe.
    Returns None if registry is unreachable — caller should fall back
    to env var or hardcoded default.
    """
    key = _cache_key(service, model_type)

    with _cache_lock:
        entry = _cache.get(key)
        if entry and _is_fresh(entry):
            return entry.get("model_id")

    # Cache miss or stale — query registry
    model_id = _query_registry(service, model_type, timeout=timeout)

    with _cache_lock:
        _cache[key] = {"model_id": model_id, "ts": time.monotonic()}

    return model_id


def invalidate_cache():
    """Clear the model cache. Call when NATS model.registry.updated.v1 fires."""
    with _cache_lock:
        _cache.clear()
    logger.info("model-registry cache invalidated")


def get_models_by_type(model_type: str, timeout: float = 5.0) -> List[Dict]:
    """
    Get all active models of a given type from the registry.
    Returns empty list if registry is unreachable.
    """
    import requests

    try:
        r = requests.get(
            f"{MODEL_REGISTRY_URL}/api/models",
            params={"model_type": model_type},
            timeout=timeout,
        )
        if r.ok:
            data = r.json()
            items = data.get("items", []) if isinstance(data, dict) else data
            return [i for i in items if i.get("active", True)]
    except Exception as e:
        logger.debug("model-registry query failed: %s", e)

    return []
