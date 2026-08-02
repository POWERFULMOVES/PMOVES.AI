#!/usr/bin/env python3
"""Configuration for the PMOVES semantic cache proxy.

All settings are env-driven (pydantic-settings). Every layer fails open —
unavailable dependencies degrade to passthrough, never block inference.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CacheSettings(BaseSettings):
    """Semantic cache configuration."""

    model_config = SettingsConfigDict(
        env_prefix="CACHE_",
        env_file=".env",
        extra="ignore",
    )

    # --- Proxy ---
    port: int = Field(default=3001, description="Proxy listen port")
    tensorzero_url: str = Field(
        default="http://tensorzero-gateway:3000/openai/v1",
        description="Upstream TensorZero OpenAI-compatible base URL",
    )

    # --- pgvector (Layer 1) ---
    database_url: str = Field(
        default="",
        description="PostgreSQL URL with pgvector (e.g. postgresql://user:pass@host/db)",
    )
    similarity_threshold: float = Field(
        default=0.90,
        description="Minimum cosine similarity for a cache hit (0.0–1.0)",
    )
    ttl_chat_secs: int = Field(default=300, description="Cache TTL for chat completions (seconds)")
    ttl_embedding_secs: int = Field(default=3600, description="Cache TTL for embeddings (seconds)")

    # --- Embeddings ---
    hirag_gateway_url: str = Field(
        default="http://hi-rag-gateway-v2:8086",
        description="Hi-RAG Gateway v2 base URL for embedding delegation",
    )
    hirag_embeddings_url: str = Field(
        default="",
        description="Direct embeddings endpoint override (if different from gateway)",
    )
    ollama_url: str = Field(
        default="http://pmoves-ollama:11434",
        description="Ollama fallback for embeddings",
    )
    embedding_model: str = Field(
        default="qwen3_embedding_4b_local",
        description="Default embedding model (TensorZero model key or Ollama model name)",
    )
    embedding_dim: int = Field(default=2560, description="Embedding dimension")

    # --- Cipher Layer 0 (Knowledge Graph pre-check) ---
    cipher_enabled: bool = Field(default=True, description="Enable Cipher Layer 0 KG pre-check")
    cipher_mcp_url: str = Field(
        default="http://localhost:8105",
        description="Cipher Memory API base URL",
    )
    cipher_api_token: str = Field(default="", description="Cipher auth token (if configured)")

    # --- Tokenism Attribution ---
    tokenism_enabled: bool = Field(default=True, description="Publish cache-hit cost savings to Tokenism")
    nats_url: str = Field(
        default="nats://nats:pmoves@nats:4222",
        description="NATS URL for Tokenism attribution events",
    )

    # --- Cache Filter (what gets cached) ---
    max_messages_for_cache: int = Field(default=3, description="Max messages in a cacheable request")
    max_temperature_for_cache: float = Field(default=0.3, description="Max temperature for cacheable request")
    cache_tools: bool = Field(default=False, description="Cache requests with tool definitions")

    # --- Circuit Breaker ---
    max_consecutive_failures: int = Field(default=5, description="Open circuit after N consecutive failures")
    circuit_reset_secs: int = Field(default=60, description="Circuit breaker reset timeout")

    @property
    def embeddings_endpoint(self) -> str:
        """Resolve the embeddings endpoint URL."""
        if self.hirag_embeddings_url:
            return self.hirag_embeddings_url
        return f"{self.hirag_gateway_url.rstrip('/')}/v1/embeddings"


@lru_cache(maxsize=1)
def get_settings() -> CacheSettings:
    """Return cached settings instance."""
    return CacheSettings()


def is_cacheable_request(body: dict[str, Any], settings: CacheSettings | None = None) -> tuple[bool, str]:
    """Determine if a request is eligible for caching.

    Returns (cacheable, reason). Only single-query, low-temperature requests
    without tools are cached (per acceptance criteria in issue #1427).
    """
    if settings is None:
        settings = get_settings()

    # Streaming requests are passthrough (MVP — no stream caching)
    if body.get("stream", False):
        return False, "stream=true"

    messages = body.get("messages", [])

    # Too many messages = multi-turn conversation
    if len(messages) > settings.max_messages_for_cache:
        return False, f"messages>{settings.max_messages_for_cache}"

    # Tool-calling requests — skip unless explicitly enabled
    if not settings.cache_tools:
        if body.get("tools") or body.get("tool_choice"):
            return False, "has_tools"

    # High temperature = creative/non-deterministic — skip
    temp = body.get("temperature", 0.0)
    if isinstance(temp, (int, float)) and temp > settings.max_temperature_for_cache:
        return False, f"temperature>{settings.max_temperature_for_cache}"

    return True, "ok"
