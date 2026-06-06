"""Jellyfin music-library source for audio grounding. Maps Jellyfin item ids
into fingerprints for provenance (links each CGP point back to its source)."""
from __future__ import annotations

import os
from typing import Optional

import httpx


class JellyfinAudioSource:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None,
                 transport: Optional[httpx.BaseTransport] = None, timeout: float = 30.0):
        self.base_url = (base_url or os.environ.get("JELLYFIN_URL", "http://localhost:8096")).rstrip("/")
        self.api_key = api_key or os.environ.get("JELLYFIN_API_KEY", "")
        self._transport = transport
        self.timeout = timeout

    def list_audio_items(self) -> list[dict]:
        params = {"IncludeItemTypes": "Audio", "Recursive": "true",
                  "Fields": "Path,RunTimeTicks", "api_key": self.api_key}
        with httpx.Client(transport=self._transport, timeout=self.timeout) as c:
            r = c.get(f"{self.base_url}/Items", params=params)
            r.raise_for_status()
            items = r.json().get("Items", [])
        return [{
            "jellyfin_item_id": it["Id"],
            "name": it.get("Name", it["Id"]),
            "file": it.get("Path", ""),
            "duration_s": round(it.get("RunTimeTicks", 0) / 1e7, 3),  # ticks(100ns) -> s
        } for it in items]
