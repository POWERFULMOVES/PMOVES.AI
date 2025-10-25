"""Helpers for retrieving geometry parameter packs from Supabase/PostgREST."""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional

import requests

_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
_LOCK = threading.RLock()
_DEFAULT_TTL = int(os.getenv("GEOMETRY_PACK_TTL", "600"))


def _rest_config() -> tuple[Optional[str], Optional[str]]:
    """Retrieves Supabase REST URL and service key from environment variables.

    Returns:
        A tuple containing the REST URL and the service key.
    """
    rest_url = os.getenv("SUPA_REST_URL") or os.getenv("SUPABASE_REST_URL")
    service_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )
    return rest_url, service_key


def _cache_key(namespace: str, modality: str, pack_type: str) -> str:
    """Creates a standardized cache key.

    Args:
        namespace: The namespace of the parameter pack.
        modality: The modality of the parameter pack.
        pack_type: The type of the parameter pack (e.g., 'cg_builder').

    Returns:
        A string to be used as a cache key.
    """
    return f"{namespace}:{modality}:{pack_type}"


def _cached_pack(key: str) -> Optional[Dict[str, Any]]:
    """Retrieves a parameter pack from the cache if it's not expired.

    Args:
        key: The cache key.

    Returns:
        The cached parameter pack dictionary, or None if not found or expired.
    """
    now = time.time()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < _DEFAULT_TTL:
            return cached[1]
    return None


def _store_pack(key: str, pack: Dict[str, Any]) -> None:
    """Stores a parameter pack in the cache.

    Args:
        key: The cache key.
        pack: The parameter pack dictionary to store.
    """
    with _LOCK:
        _CACHE[key] = (time.time(), pack)


def _fetch_pack(namespace: str, modality: str, pack_type: str) -> Optional[Dict[str, Any]]:
    """Fetches the latest active parameter pack from Supabase.

    Args:
        namespace: The namespace of the parameter pack.
        modality: The modality of the parameter pack.
        pack_type: The type of the parameter pack.

    Returns:
        The fetched parameter pack dictionary, or None on failure.
    """
    rest_url, service_key = _rest_config()
    if not rest_url:
        return None

    params = {
        "select": "id,params,status,population_id,generation,fitness,energy,version",
        "namespace": f"eq.{namespace}",
        "modality": f"eq.{modality}",
        "pack_type": f"eq.{pack_type}",
        "status": "eq.active",
        "order": "created_at.desc",
        "limit": "1",
    }
    headers = {"Accept": "application/json"}
    if service_key:
        headers.update({"apikey": service_key, "Authorization": f"Bearer {service_key}"})

    base_url = rest_url.rstrip("/")
    url = f"{base_url}/geometry_parameter_packs"
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10.0)
        resp.raise_for_status()
        rows = resp.json()
    except Exception:
        return None

    if not isinstance(rows, list) or not rows:
        return None

    pack = rows[0]
    if isinstance(pack, dict):
        return pack
    return None


def get_builder_pack(namespace: str, modality: str) -> Optional[Dict[str, Any]]:
    """Fetch the latest active builder parameter pack for the namespace/modality."""

    key = _cache_key(namespace, modality, "cg_builder")
    cached = _cached_pack(key)
    if cached is not None:
        return cached

    pack = _fetch_pack(namespace, modality, "cg_builder")
    if pack is None:
        return None
    _store_pack(key, pack)
    return pack


def get_decoder_pack(namespace: str, modality: str) -> Optional[Dict[str, Any]]:
    """Retrieves the latest active decoder parameter pack for a namespace and modality.

    This function uses a time-based cache to avoid repeated requests to Supabase.

    Args:
        namespace: The namespace of the parameter pack.
        modality: The modality of the parameter pack.

    Returns:
        The decoder parameter pack dictionary, or None if not found.
    """

    key = _cache_key(namespace, modality, "decoder")
    cached = _cached_pack(key)
    if cached is not None:
        return cached

    pack = _fetch_pack(namespace, modality, "decoder")
    if pack is None:
        return None
    _store_pack(key, pack)
    return pack


def clear_cache() -> None:
    """Clears the in-memory cache of parameter packs."""
    with _LOCK:
        _CACHE.clear()
