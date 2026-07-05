"""Thin client for clap-embed (:8108). On any failure returns None and sets
last_grounding='partial' so the caller can degrade to librosa-only, flagged."""
from __future__ import annotations

import os
from typing import Optional

import httpx


class ClapClient:
    def __init__(self, base_url: Optional[str] = None, transport: Optional[httpx.BaseTransport] = None, timeout: float = 30.0):
        self.base_url = (base_url or os.environ.get("CLAP_EMBED_URL", "http://localhost:8108")).rstrip("/")
        self._transport = transport
        self.timeout = timeout
        self.last_grounding = "full"

    def embed_audio_bytes(self, data: bytes, filename: str) -> Optional[list[float]]:
        try:
            with httpx.Client(transport=self._transport, timeout=self.timeout) as c:
                r = c.post(f"{self.base_url}/embed/audio",
                           files={"file": (filename, data, "audio/wav")})
                r.raise_for_status()
                self.last_grounding = "full"
                return r.json()["embedding"]
        except Exception:
            self.last_grounding = "partial"
            return None
