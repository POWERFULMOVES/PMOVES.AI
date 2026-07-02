#!/usr/bin/env python3
"""Async embedding client — Hi-RAG Gateway primary, Ollama fallback.

Fail-open: returns None on any error so callers degrade to passthrough.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from config import CacheSettings, get_settings

logger = logging.getLogger(__name__)


class HiragEmbeddingClient:
    """Delegates embedding generation to Hi-RAG Gateway with Ollama fallback."""

    def __init__(self, settings: CacheSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.AsyncClient(timeout=30.0)
        self._consecutive_failures = 0

    @property
    def circuit_open(self) -> bool:
        """Circuit breaker: open after max_consecutive_failures."""
        return self._consecutive_failures >= self.settings.max_consecutive_failures

    async def embed(self, text: str, model: str | None = None) -> Optional[list[float]]:
        """Generate embedding via Hi-RAG Gateway, fallback to Ollama.

        Returns None on any failure (fail-open).
        """
        if self.circuit_open:
            logger.warning("Embedding circuit breaker open — skipping")
            return None

        model = model or self.settings.embedding_model

        # Primary: Hi-RAG Gateway
        embedding = await self._try_endpoint(
            self.settings.embeddings_endpoint, text, model
        )
        if embedding is not None:
            return embedding

        # Fallback: Ollama OpenAI-compatible endpoint
        ollama_url = f"{self.settings.ollama_url.rstrip('/')}/v1/embeddings"
        return await self._try_endpoint(ollama_url, text, model)

    async def _try_endpoint(
        self, url: str, text: str, model: str
    ) -> Optional[list[float]]:
        """Attempt embedding at a single endpoint."""
        try:
            resp = await self._client.post(
                url,
                json={"input": text, "model": model},
            )
            resp.raise_for_status()
            data = resp.json()
            self._consecutive_failures = 0
            # OpenAI-compatible response format
            return data["data"][0]["embedding"]
        except Exception as exc:
            logger.warning("Embedding endpoint %s failed: %s", url, exc)
            self._consecutive_failures += 1
            return None

    async def close(self) -> None:
        await self._client.aclose()
