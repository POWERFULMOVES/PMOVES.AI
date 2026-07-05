#!/usr/bin/env python3
"""Layer 0: Cipher Knowledge Graph pre-check.

Queries the Cipher Memory API before pgvector. Stores cache misses
for future KG-based hits. Fire-and-forget, fail-open.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

import httpx

from config import CacheSettings, get_settings

logger = logging.getLogger(__name__)


class CipherLayer:
    """Cipher KG pre-check and post-store integration."""

    def __init__(self, settings: CacheSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.AsyncClient(timeout=5.0)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.settings.cipher_api_token:
            headers["Authorization"] = f"Bearer {self.settings.cipher_api_token}"
        return headers

    @property
    def base_url(self) -> str:
        return self.settings.cipher_mcp_url.rstrip("/")

    async def search(self, query: str) -> Optional[dict[str, Any]]:
        """Pre-check: search Cipher KG for a matching context.

        Returns matching memory dict or None. Fail-open on any error.
        """
        if not self.settings.cipher_enabled:
            return None
        try:
            resp = await self._client.get(
                f"{self.base_url}/api/memory/search",
                params={"q": query, "limit": 1},
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", data) if isinstance(data, dict) else data
            if isinstance(results, list) and results:
                return results[0]
            return None
        except Exception as exc:
            logger.debug("Cipher search failed (fail-open): %s", exc)
            return None

    async def store(self, query: str, response: dict[str, Any]) -> None:
        """Post-store: record cache miss in Cipher KG for future hits.

        Fire-and-forget, fail-open.
        """
        if not self.settings.cipher_enabled:
            return
        try:
            resp_hash = hashlib.sha256(
                json.dumps(response, sort_keys=True).encode()
            ).hexdigest()[:16]
            await self._client.post(
                f"{self.base_url}/api/memory",
                json={
                    "content": query,
                    "category": "context",
                    "tags": ["semantic-cache"],
                    "metadata": {
                        "response_hash": resp_hash,
                        "source": "semantic-cache",
                    },
                },
                headers=self._headers(),
            )
        except Exception as exc:
            logger.debug("Cipher store failed (fail-open): %s", exc)

    async def close(self) -> None:
        await self._client.aclose()
