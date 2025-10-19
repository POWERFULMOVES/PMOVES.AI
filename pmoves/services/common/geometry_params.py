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


def get_builder_pack(namespace: str, modality: str) -> Optional[Dict[str, Any]]:
    """Fetch the latest active builder parameter pack for the namespace/modality."""

    key = f"{namespace}:{modality}:cg_builder"
    now = time.time()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < _DEFAULT_TTL:
            return cached[1]

    rest_url, service_key = _rest_config()
    if not rest_url:
        return None

    params = {
        "select": "id,params,status,population_id,generation,fitness,energy",
        "namespace": f"eq.{namespace}",
        "modality": f"eq.{modality}",
        "pack_type": "eq.cg_builder",
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
        with _LOCK:
            _CACHE[key] = (now, pack)
    return pack


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()
