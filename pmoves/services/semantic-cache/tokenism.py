#!/usr/bin/env python3
"""NATS publisher for cache-hit cost-savings attribution.

Publishes to tokenism.attribution.recorded.v1 on cache hits.
Fire-and-forget, fail-open.
"""

from __future__ import annotations

import json
import logging

from config import CacheSettings, get_settings

logger = logging.getLogger(__name__)


class TokenismPublisher:
    """Publishes attribution events to NATS for Tokenism cost tracking."""

    SUBJECT = "tokenism.attribution.recorded.v1"

    def __init__(self, settings: CacheSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._nc = None

    async def _ensure_connected(self) -> bool:
        """Lazily connect to NATS. Returns False if unavailable."""
        if self._nc is not None:
            return True
        if not self.settings.tokenism_enabled:
            return False
        try:
            from nats import connect as nats_connect

            self._nc = await nats_connect(self.settings.nats_url)
            return True
        except Exception as exc:
            logger.debug("NATS connection failed (fail-open): %s", exc)
            self._nc = None
            return False

    async def publish_attribution(
        self,
        agent_id: str,
        tokens_saved: int,
        cost_saved_usd: float,
        cache_key: str,
    ) -> None:
        """Publish a cache-hit attribution event."""
        if not await self._ensure_connected():
            return
        try:
            payload = {
                "agent_id": agent_id,
                "tokens_saved": tokens_saved,
                "cost_saved_usd": cost_saved_usd,
                "cache_key": cache_key,
            }
            await self._nc.publish(
                self.SUBJECT, json.dumps(payload).encode()
            )
        except Exception as exc:
            logger.debug("Tokenism publish failed (fail-open): %s", exc)

    async def close(self) -> None:
        if self._nc is not None:
            try:
                await self._nc.close()
            except Exception:
                pass
            self._nc = None
