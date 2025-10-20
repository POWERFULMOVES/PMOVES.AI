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
    rest_url = os.getenv("SUPA_REST_URL") or os.getenv("SUPABASE_REST_URL")
    service_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )
    return rest_url, service_key


def _cache_key(namespace: str, modality: str, pack_type: str) -> str:
    return f"{namespace}:{modality}:{pack_type}"


def _cached_pack(key: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < _DEFAULT_TTL:
            return cached[1]
    return None


def _store_pack(key: str, pack: Dict[str, Any]) -> None:
    with _LOCK:
        _CACHE[key] = (time.time(), pack)


def _fetch_pack(namespace: str, modality: str, pack_type: str) -> Optional[Dict[str, Any]]:
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
    """Fetch the latest active decoder parameter pack, when present."""

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
    with _LOCK:
        _CACHE.clear()
