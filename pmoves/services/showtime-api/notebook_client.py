"""Open Notebook API client.

Polls the Open Notebook API and returns a paginated feed
of notebooks for the Showtime dashboard.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("showtime.notebook_client")


try:
    from pmoves.services.common.env import get_secret
except ModuleNotFoundError:
    # Runtime fallback for direct script execution where repo root is not on sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from pmoves.services.common.env import get_secret


NOTEBOOK_API_URL = os.environ.get("OPEN_NOTEBOOK_API_URL", "http://localhost:5055")
# OPEN_NOTEBOOK_API_TOKEN is the repo-standard variable.
# Keep OPEN_NOTEBOOK_PASSWORD / OPEN_NOTEBOOK_API_KEY as compatibility fallbacks.
NOTEBOOK_API_TOKEN = (
    (get_secret("OPEN_NOTEBOOK_API_TOKEN") or "").strip()
    or (get_secret("OPEN_NOTEBOOK_PASSWORD") or "").strip()
    or (get_secret("OPEN_NOTEBOOK_API_KEY") or "").strip()
)
CACHE_TTL = int(os.environ.get("NOTEBOOK_CACHE_TTL", "60"))

# Simple in-memory cache: key -> (timestamp, data)
_cache: dict[str, tuple[float, Any]] = {}
MAX_CACHE_ENTRIES = 100


async def fetch_notebooks(cursor: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Fetch notebooks from Open Notebook API with caching."""
    global _cache

    cache_key = f"{cursor}:{limit}"
    now = time.time()

    if cache_key in _cache:
        cached_ts, cached_data = _cache[cache_key]
        if (now - cached_ts) < CACHE_TTL:
            return cached_data

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if NOTEBOOK_API_TOKEN:
        headers["Authorization"] = f"Bearer {NOTEBOOK_API_TOKEN}"

    params: dict[str, Any] = {"limit": limit}
    if cursor:
        params["cursor"] = cursor

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{NOTEBOOK_API_URL}/api/notebooks",
                headers=headers,
                params=params,
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Notebook API HTTP error: %s", exc.response.status_code)
        return {"items": [], "cursor": None, "error": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        logger.error("Notebook API connection error: %s", type(exc).__name__)
        return {"items": [], "cursor": None, "error": "Notebook API error"}

    # Normalize response
    items = data if isinstance(data, list) else data.get("items", data.get("notebooks", []))
    result = {
        "items": [
            {
                "id": item.get("id", ""),
                "title": item.get("title", item.get("name", "Untitled")),
                "type": item.get("type", "notebook"),
                "preview": (item.get("content", "") or "")[:200],
                "created_at": item.get("created_at", item.get("createdAt", "")),
                "updated_at": item.get("updated_at", item.get("updatedAt", "")),
            }
            for item in (items[:limit] if isinstance(items, list) else [])
        ],
        "cursor": data.get("next_cursor", data.get("cursor")) if isinstance(data, dict) else None,
    }

    # Evict oldest entries if cache is full
    if len(_cache) >= MAX_CACHE_ENTRIES:
        oldest_key = min(_cache, key=lambda k: _cache[k][0])
        del _cache[oldest_key]

    _cache[cache_key] = (now, result)
    return result
