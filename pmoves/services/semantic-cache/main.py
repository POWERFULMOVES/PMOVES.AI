#!/usr/bin/env python3
"""PMOVES Semantic Cache Proxy — FastAPI application.

Intercepts OpenAI-compatible chat completions between agents and TensorZero.
Three-layer cache: Cipher KG → pgvector → passthrough.
All layers fail-open (Circuit Breaker principle).
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from cache_store import CacheStore, build_cache_key
from cipher_layer import CipherLayer
from config import CacheSettings, get_settings, is_cacheable_request
from hirag_client import HiragEmbeddingClient
from metrics import (
    cache_errors_total,
    cache_hits_total,
    cache_misses_total,
    cache_similarity_score,
)
from tokenism import TokenismPublisher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown of all cache components."""
    settings = get_settings()
    app.state.settings = settings
    app.state.cache_store = CacheStore(settings)
    app.state.hirag_client = HiragEmbeddingClient(settings)
    app.state.cipher = CipherLayer(settings)
    app.state.tokenism = TokenismPublisher(settings)
    app.state.http = httpx.AsyncClient(timeout=120.0)
    logger.info("Semantic cache proxy started on :%d", settings.port)
    yield
    # Cleanup
    await app.state.cache_store.close()
    await app.state.hirag_client.close()
    await app.state.cipher.close()
    await app.state.tokenism.close()
    await app.state.http.aclose()
    logger.info("Semantic cache proxy stopped")


app = FastAPI(title="PMOVES Semantic Cache", lifespan=lifespan)


def _extract_query_text(body: dict[str, Any]) -> str:
    """Extract last user message as the query for embedding."""
    messages = body.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                # Extract text from content parts
                texts = [
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                return " ".join(texts)
            return str(content)
    return ""


def _estimate_tokens(response: dict[str, Any]) -> int:
    """Estimate tokens saved from a cached response."""
    usage = response.get("usage", {})
    return usage.get("total_tokens", 0)


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {"status": "ok", "service": "semantic-cache"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/openai/v1/chat/completions")
async def chat_completions(request: Request):
    """Intercept, cache-check, proxy to TensorZero."""
    settings: CacheSettings = request.app.state.settings
    cache_store: CacheStore = request.app.state.cache_store
    hirag: HiragEmbeddingClient = request.app.state.hirag_client
    cipher: CipherLayer = request.app.state.cipher
    tokenism: TokenismPublisher = request.app.state.tokenism
    http: httpx.AsyncClient = request.app.state.http

    # Parse body
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Extract forwarded headers (strip hop-by-hop)
    fwd_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length", "transfer-encoding"}
    }

    upstream_url = f"{settings.tensorzero_url.rstrip('/')}/chat/completions"

    # --- Check cacheability ---
    cacheable, reason = is_cacheable_request(body, settings)
    if not cacheable:
        logger.debug("Passthrough (not cacheable): %s", reason)
        return await _proxy(http, upstream_url, body, fwd_headers)

    # --- SSE streaming passthrough ---
    if body.get("stream", False):
        return await _proxy_stream(http, upstream_url, body, fwd_headers)

    # --- Extract query text ---
    query_text = _extract_query_text(body)
    if not query_text:
        return await _proxy(http, upstream_url, body, fwd_headers)

    try:
        # --- Layer 0: Cipher KG pre-check ---
        cipher_hit = await cipher.search(query_text)
        if cipher_hit is not None:
            cached_response = cipher_hit.get("metadata", {}).get("response")
            if cached_response:
                cache_hits_total.inc()
                logger.info("Cipher KG hit for query: %s", query_text[:80])
                return JSONResponse(content=cached_response)

        # --- Layer 1: pgvector semantic lookup ---
        embedding = await hirag.embed(query_text)
        if embedding is not None:
            result = await cache_store.lookup(
                embedding, body.get("model", ""), settings.similarity_threshold
            )
            if result is not None:
                cache_hits_total.inc()
                cache_similarity_score.observe(result["similarity"])

                # Tokenism attribution (fire-and-forget)
                tokens_saved = result.get("tokens_saved") or _estimate_tokens(result["response"])
                await tokenism.publish_attribution(
                    agent_id=fwd_headers.get("x-pmoves-agent", "unknown"),
                    tokens_saved=tokens_saved,
                    cost_saved_usd=tokens_saved * 0.00001,
                    cache_key=build_cache_key(body),
                )

                logger.info(
                    "Cache HIT (similarity=%.4f) for: %s",
                    result["similarity"], query_text[:80],
                )
                return JSONResponse(content=result["response"])

        # --- Cache MISS: proxy to TensorZero ---
        cache_misses_total.inc()
        logger.debug("Cache MISS for: %s", query_text[:80])

        response = await _proxy_raw(http, upstream_url, body, fwd_headers)

        # --- Store response in cache (best-effort) ---
        if response is not None and embedding is not None:
            cache_key = build_cache_key(body)
            await cache_store.store(
                cache_key=cache_key,
                query=query_text,
                embedding=embedding,
                model=body.get("model", ""),
                response=response,
                ttl=settings.ttl_chat_secs,
            )
            # Store in Cipher KG for future Layer 0 hits
            await cipher.store(query_text, response)

        if response is not None:
            return JSONResponse(content=response)
        # _proxy_raw failed — fallback already returned inside _proxy
        return JSONResponse(content={"error": "upstream_failed"}, status_code=502)

    except Exception as exc:
        # Fail-open: any cache error → passthrough
        cache_errors_total.inc()
        logger.warning("Cache pipeline error (fail-open): %s", exc)
        return await _proxy(http, upstream_url, body, fwd_headers)


async def _proxy(
    http: httpx.AsyncClient,
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
) -> JSONResponse:
    """Non-streaming proxy to TensorZero."""
    try:
        resp = await http.post(url, json=body, headers=headers)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as exc:
        logger.error("Upstream proxy failed: %s", exc)
        return JSONResponse(content={"error": str(exc)}, status_code=502)


async def _proxy_raw(
    http: httpx.AsyncClient,
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any] | None:
    """Non-streaming proxy returning raw dict (or None on failure)."""
    try:
        resp = await http.post(url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Upstream proxy_raw failed: %s", exc)
        return None


async def _proxy_stream(
    http: httpx.AsyncClient,
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
) -> StreamingResponse:
    """SSE streaming passthrough (no caching)."""

    async def stream_generator():
        try:
            async with http.stream(
                "POST", url, json=body, headers=headers
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk
        except Exception as exc:
            logger.error("Stream proxy failed: %s", exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n".encode()

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=get_settings().port)
