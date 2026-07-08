"""
Semantic Cache Proxy for PMOVES.AI LLM Inference
=================================================

Issue #1427: Intercepts OpenAI-compatible requests, checks Cipher (Layer 0)
and pgvector (Layer 1) for semantically similar cached queries, returns on hit
or forwards to TensorZero. Embeddings generated via Hi-RAG Gateway v2.

Architecture
------------
┌─────────────────────────────────────────────────────────────────────┐
│                     PMOVES Semantic Cache Proxy                      │
│                                                                      │
│   Client Request                                                     │
│       │                                                              │
│       ▼                                                              │
│   ┌──────────────┐    HIT ──► ┌──────────────────────────────┐     │
│   │  Cipher L0   │ ──────────►│   Return Cached Response     │     │
│   │  (Memory)    │    MISS    └──────────────────────────────┘     │
│   └──────┬───────┘                                                  │
│          │ MISS                                                     │
│          ▼                                                          │
│   ┌──────────────┐    HIT ──► ┌──────────────────────────────┐     │
│   │  pgvector L1 │ ──────────►│   Return Cached Response     │     │
│   │  (Semantic)  │    MISS    └──────────────────────────────┘     │
│   └──────┬───────┘                                                  │
│          │ MISS                                                     │
│          ▼                                                          │
│   ┌────────────────────────────────────────────────────────────┐   │
│   │              Forward to TensorZero (LLM)                   │   │
│   └──────┬───────────────────────────────────────────────────┘   │
│          │                                                          │
│          ▼                                                          │
│   ┌────────────────────────────────────────────────────────────┐   │
│   │  Store response in L1 (pgvector) + L0 (Cipher) + LRU       │   │
│   └────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   CHIT Bus: NATS subscription for cross-instance invalidation        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

Layers
------
- Layer 0 (Cipher): In-memory exact/semantic pre-check via Cipher MCP.
- Layer 1 (pgvector): Vector similarity search via Supabase pgvector.
- Hi-RAG Gateway v2: Embedding generation with Ollama fallback.
- CHIT Bus: NATS-based cache invalidation across proxy instances.

Fail-Open Design
----------------
All cache failures (embedding, lookup, storage) fall through to TensorZero
without blocking the user request. Cache operations are fire-and-forget on
the hot path.

PMOVES Standards
----------------
- pydantic settings: ``.config.settings``
- prometheus metrics: ``.metrics.*``
- fail-open: never block on cache failure
- comprehensive logging: structured logs at every decision point
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from .cache_store import CacheStore
from .cipher_layer import CipherLayer
from .hirag_client import HiRAGClient
from .config import settings
from .metrics import (
    cache_hits_total,
    cache_misses_total,
    cache_similarity_score,
    cache_lookup_duration,
    cache_layer0_hits_total,
    cache_layer0_misses_total,
    cache_evictions_total,
    cache_storage_errors_total,
    cache_invalidations_total,
    tensorzero_forward_duration,
    tensorzero_forward_errors_total,
    streaming_requests_total,
)

logger = logging.getLogger(__name__)

# ── Shared global clients (initialised in lifespan) ──────────────────────
http_client: httpx.AsyncClient
hirag_client: HiRAGClient          # Hi-RAG Gateway v2 embedding backend
cipher: CipherLayer                # Cipher Layer 0 pre-check
cache: CacheStore                  # pgvector Layer 1

# NATS connection for CHIT Bus cache invalidation (optional)
_nats_client: Optional[Any] = None


# ═══════════════════════════════════════════════════════════════════════════
# Lifespan manager
# ═══════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise and tear-down shared clients for the semantic cache."""
    global http_client, hirag_client, cipher, cache, _nats_client

    logger.info("[lifespan] Starting PMOVES Semantic Cache Proxy …")
    startup_t0 = time.monotonic()

    # ── 1. HTTP client for TensorZero forwarding ──────────────────────────
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=10.0,
            read=120.0,
            write=30.0,
            pool=5.0,
        ),
        limits=httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
        ),
    )
    logger.info("[lifespan] HTTP client initialised")

    # ── 2. Hi-RAG Gateway v2 (embeddings) ────────────────────────────────
    hirag_client = HiRAGClient(
        base_url=settings.hirag_gateway_url,
        fallback_url=settings.tensorzero_url,  # fail-open to Ollama via TensorZero
    )
    await hirag_client.init()
    logger.info(
        "[lifespan] Hi-RAG client initialised: base=%s fallback=%s",
        settings.hirag_gateway_url,
        settings.tensorzero_url,
    )

    # ── 3. Cipher Layer 0 ────────────────────────────────────────────────
    cipher = CipherLayer(
        mcp_endpoint=settings.cipher_mcp_url,
        enabled=settings.cipher_layer_enabled,
    )
    await cipher.init()
    logger.info(
        "[lifespan] Cipher Layer 0 initialised: enabled=%s",
        cipher.enabled,
    )

    # ── 4. pgvector Layer 1 ──────────────────────────────────────────────
    cache = CacheStore(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_key,
        hirag_client=hirag_client,  # delegate embedding to Hi-RAG
    )
    await cache.init()
    logger.info("[lifespan] CacheStore (pgvector L1) initialised")

    # ── 5. CHIT Bus: NATS cache invalidation subscription ────────────────
    if settings.chit_bus_enabled:
        try:
            import nats
            _nats_client = await nats.connect(
                servers=[settings.nats_url],
                name="semantic-cache-proxy",
                reconnect_time_wait=5,
                max_reconnect_attempts=10,
            )
            asyncio.create_task(_subscribe_cache_invalidation())
            logger.info("[lifespan] CHIT Bus NATS subscriber started: %s", settings.nats_url)
        except Exception as exc:
            logger.warning("[lifespan] CHIT Bus NATS unavailable (non-blocking): %s", exc)
            _nats_client = None
    else:
        logger.info("[lifespan] CHIT Bus disabled via configuration")

    elapsed = time.monotonic() - startup_t0
    logger.info("[lifespan] Startup complete in %.3f s — accepting requests", elapsed)

    yield  # ── Application runs here ──────────────────────────────────────

    # ── Teardown ──────────────────────────────────────────────────────────
    logger.info("[lifespan] Shutting down PMOVES Semantic Cache Proxy …")
    await http_client.aclose()
    await hirag_client.close()
    await cipher.close()
    await cache.close()
    if _nats_client is not None:
        await _nats_client.close()
        logger.info("[lifespan] NATS client closed")
    logger.info("[lifespan] Shutdown complete")


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI application
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="PMOVES Semantic Cache",
    description="OpenAI-compatible semantic cache proxy with Hi-RAG embeddings",
    version="2.0.0",
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/openai/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    """
    Intercept chat completion requests with three-layer cache lookup.

    Layer 0 — Cipher Memory Pre-Check (exact/fuzzy, cross-session)
    Layer 1 — pgvector Semantic Search (cosine similarity)
    Forward — TensorZero on miss, with async cache population
    """
    request_t0 = time.monotonic()
    request_id = _generate_request_id()

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        logger.exception("[%s] Invalid JSON in request body", request_id)
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": "Invalid JSON in request body",
                    "type": "invalid_request_error",
                    "code": "invalid_json",
                }
            },
        )

    model = body.get("model", "unknown")
    is_streaming = body.get("stream", False)

    logger.info(
        "[%s] chat/completions request: model=%s stream=%s messages=%d",
        request_id,
        model,
        is_streaming,
        len(body.get("messages", [])),
    )

    # ── Streaming requests: passthrough (no caching) ──────────────────────
    if is_streaming:
        streaming_requests_total.labels(model=model).inc()
        logger.info("[%s] Streaming request — passthrough to TensorZero", request_id)
        return await _forward_streaming(body, request_id)

    # ── Filter: only cache cacheable requests ─────────────────────────────
    if not _is_cacheable(body):
        logger.info("[%s] Request not cacheable — passthrough", request_id)
        return await _forward_passthrough(body, request_id=request_id)

    query_text = _extract_query_text(body)
    if not query_text:
        logger.info("[%s] Empty query text — passthrough", request_id)
        return await _forward_passthrough(body, request_id=request_id)

    logger.debug("[%s] Extracted query text: %r", request_id, query_text[:200])

    # ═══════════════════════════════════════════════════════════════════════
    # Layer 0: Cipher Memory Pre-Check
    # ═══════════════════════════════════════════════════════════════════════
    if cipher.enabled:
        t0 = time.monotonic()
        try:
            cipher_result = await cipher.search(query_text, model)
        except Exception as exc:
            logger.warning("[%s] Cipher L0 lookup failed (fail-open): %s", request_id, exc)
            cipher_result = None
        duration = time.monotonic() - t0

        if cipher_result:
            # Layer 0 HIT: return immediately, skip embedding + pgvector
            cache_layer0_hits_total.labels(model=model).inc()
            cache_lookup_duration.labels(status="layer0_hit").observe(duration)
            logger.info(
                "[%s] LAYER 0 HIT (Cipher): similarity=%.4f duration=%.4f",
                request_id,
                cipher_result.get("similarity_score", 1.0),
                duration,
            )
            return _build_cached_response(cipher_result, body, request_id)

        cache_layer0_misses_total.labels(model=model).inc()
        cache_lookup_duration.labels(status="layer0_miss").observe(duration)
        logger.debug("[%s] Layer 0 miss (Cipher): duration=%.4f", request_id, duration)

    # ═══════════════════════════════════════════════════════════════════════
    # Step 1: Embed the query via Hi-RAG Gateway v2
    # ═══════════════════════════════════════════════════════════════════════
    embed_t0 = time.monotonic()
    try:
        embedding = await hirag_client.embed(query_text)
    except Exception as exc:
        logger.error("[%s] Hi-RAG embedding failed (fail-open): %s", request_id, exc)
        embedding = None
    embed_duration = time.monotonic() - embed_t0

    if embedding is None:
        # Embedding failed — fail-open to TensorZero
        logger.info("[%s] Embedding failed — passthrough to TensorZero", request_id)
        return await _forward_passthrough(body, request_id=request_id)

    logger.debug(
        "[%s] Embedding generated: dim=%d duration=%.4f",
        request_id,
        len(embedding),
        embed_duration,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Layer 1: Semantic cache lookup (pgvector)
    # ═══════════════════════════════════════════════════════════════════════
    t1 = time.monotonic()
    cached: Optional[dict[str, Any]] = None
    try:
        cached = await cache.lookup(
            embedding=embedding,
            model=model,
            threshold=settings.similarity_threshold,
        )
    except Exception as exc:
        logger.warning("[%s] pgvector L1 lookup failed (fail-open): %s", request_id, exc)
    duration = time.monotonic() - t1
    cache_lookup_duration.labels(status="hit" if cached else "miss").observe(duration)

    if cached:
        # Layer 1 HIT: return cached response
        cache_hits_total.labels(model=model).inc()
        similarity = cached.get("similarity_score", 0.0)
        cache_similarity_score.labels(model=model).set(similarity)
        logger.info(
            "[%s] LAYER 1 HIT (pgvector): id=%s similarity=%.4f duration=%.4f",
            request_id,
            cached.get("id", "?"),
            similarity,
            duration,
        )

        # Increment hit counter (fire-and-forget)
        try:
            await cache.increment_hit(cached["id"])
        except Exception as exc:
            logger.debug("[%s] increment_hit failed (non-critical): %s", request_id, exc)

        return _build_cached_response(cached, body, request_id)

    # ── MISS ──────────────────────────────────────────────────────────────
    cache_misses_total.labels(model=model).inc()
    logger.info(
        "[%s] CACHE MISS — forwarding to TensorZero (L0+L1 miss)",
        request_id,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Forward to TensorZero and capture response for caching
    # ═══════════════════════════════════════════════════════════════════════
    response = await _forward_and_capture(body, request_id)

    if response is None:
        logger.error("[%s] TensorZero forward returned None", request_id)
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": "Upstream service unavailable",
                    "type": "proxy_error",
                    "code": "tensorzero_unavailable",
                }
            },
        )

    # ── Store in cache layers (async, non-blocking) ───────────────────────
    if response.status_code == 200:
        try:
            response_text = response.text
        except Exception:
            response_text = ""

        if response_text:
            asyncio.create_task(
                _store_all_layers(
                    request_id=request_id,
                    query_text=query_text,
                    query_embedding=embedding,
                    response_text=response_text,
                    model=model,
                    ttl_seconds=settings.cache_ttl_chat_secs,
                )
            )
            logger.debug("[%s] Cache population task created", request_id)

        total_duration = time.monotonic() - request_t0
        logger.info(
            "[%s] Forward complete: status=%d total_duration=%.4f",
            request_id,
            response.status_code,
            total_duration,
        )

        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type="application/json",
            headers=dict(response.headers),
        )

    # Non-200 from TensorZero: pass through as-is
    logger.warning(
        "[%s] TensorZero returned non-200: status=%d body=%.200s",
        request_id,
        response.status_code,
        response.text,
    )
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type="application/json",
        headers=dict(response.headers),
    )


@app.post("/openai/v1/embeddings")
async def embeddings(request: Request) -> Response:
    """
    Embeddings endpoint — forward to TensorZero.

    Higher-TTL caching is optional and can be added later for embedding
    workloads that exhibit temporal locality (e.g., RAG chunking batches).
    """
    request_id = _generate_request_id()
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        logger.exception("[%s] Invalid JSON in embeddings request", request_id)
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": "Invalid JSON in request body",
                    "type": "invalid_request_error",
                    "code": "invalid_json",
                }
            },
        )

    logger.info(
        "[%s] embeddings request: model=%s inputs=%d",
        request_id,
        body.get("model", "unknown"),
        len(body.get("input", [])),
    )
    return await _forward_passthrough(
        body,
        path="/openai/v1/embeddings",
        request_id=request_id,
    )


@app.get("/metrics")
async def prometheus_metrics() -> Response:
    """Prometheus metrics endpoint for cache observability."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health() -> dict[str, Any]:
    """
    Health check endpoint.

    Returns component status including cache entry count, active Hi-RAG
    model, and Cipher Layer 0 availability.
    """
    health_status: dict[str, Any] = {
        "status": "ok",
        "version": "2.0.0",
        "components": {},
    }

    # HTTP client
    health_status["components"]["http_client"] = {
        "status": "ok" if not http_client.is_closed else "error",
    }

    # Hi-RAG
    try:
        hirag_model = await hirag_client.get_current_model()
        health_status["components"]["hirag"] = {
            "status": "ok",
            "model": hirag_model,
        }
    except Exception:
        logger.exception("Health check failed for Hi-RAG component")
        health_status["components"]["hirag"] = {
            "status": "error",
            "detail": "Hi-RAG health check failed",
        }

    # Cipher
    health_status["components"]["cipher"] = {
        "status": "ok" if cipher.enabled else "disabled",
        "enabled": cipher.enabled,
    }

    # Cache
    try:
        entry_count = await cache.count()
        health_status["components"]["cache"] = {
            "status": "ok",
            "entries": entry_count,
        }
        health_status["cache_entries"] = entry_count
    except Exception:
        logger.exception("Health check failed for cache component")
        health_status["components"]["cache"] = {
            "status": "error",
            "detail": "Cache health check failed",
        }
        health_status["cache_entries"] = -1

    # NATS / CHIT Bus
    if _nats_client is not None:
        health_status["components"]["chit_bus"] = {
            "status": "connected" if _nats_client.is_connected else "disconnected",
        }
    else:
        health_status["components"]["chit_bus"] = {
            "status": "disabled",
        }

    # Overall status
    any_error = any(
        c.get("status") == "error"
        for c in health_status["components"].values()
    )
    if any_error:
        health_status["status"] = "degraded"

    return health_status


# ═══════════════════════════════════════════════════════════════════════════
# Cache storage with LRU eviction
# ═══════════════════════════════════════════════════════════════════════════

async def _store_all_layers(
    *,
    request_id: str,
    query_text: str,
    query_embedding: list[float],
    response_text: str,
    model: str,
    ttl_seconds: int,
) -> None:
    """
    Store cache miss in both pgvector (Layer 1) and Cipher (Layer 0).

    After storing, checks cache size and evicts oldest entries if over
    the configured maximum (LRU eviction).
    """
    logger.debug("[%s] Storing cache entry in all layers …", request_id)

    # ── Layer 1: pgvector ────────────────────────────────────────────────
    try:
        await cache.store(
            query_text=query_text,
            query_embedding=query_embedding,
            response_text=response_text,
            model=model,
            ttl_seconds=ttl_seconds,
        )
        logger.debug("[%s] Layer 1 (pgvector) store OK", request_id)
    except Exception as exc:
        cache_storage_errors_total.labels(layer="pgvector").inc()
        logger.warning("[%s] Layer 1 store failed: %s", request_id, exc)

    # ── LRU Eviction: check size and trim if over limit ──────────────────
    try:
        evicted = await cache.evict_if_over_limit()
        if evicted:
            cache_evictions_total.labels(model=model, reason="lru").inc()
            logger.info("[%s] LRU eviction: removed %d entries", request_id, evicted)
    except Exception as exc:
        logger.debug("[%s] LRU eviction check failed (non-critical): %s", request_id, exc)

    # ── Layer 0: Cipher memory (for future cross-session retrieval) ──────
    if cipher.enabled:
        try:
            await cipher.store(
                query_text=query_text,
                response_text=response_text,
                model=model,
                ttl_seconds=ttl_seconds,
            )
            logger.debug("[%s] Layer 0 (Cipher) store OK", request_id)
        except Exception as exc:
            cache_storage_errors_total.labels(layer="cipher").inc()
            logger.warning("[%s] Layer 0 store failed: %s", request_id, exc)

    logger.debug("[%s] Cache storage complete", request_id)


# ═══════════════════════════════════════════════════════════════════════════
# CHIT Bus: NATS cache invalidation subscription
# ═══════════════════════════════════════════════════════════════════════════

async def _subscribe_cache_invalidation() -> None:
    """
    Subscribe to CHIT Bus NATS topic for cross-instance cache invalidation.

    This stub is ready for integration with ``Cache_CHIT_Integrator``.
    Expected message format::

        {
            "action": "invalidate",
            "scope": "layer0" | "layer1" | "all",
            "query_hash": "<sha256_hex>",
            "timestamp": "<ISO-8601>"
        }

    Handles connection drops via NATS auto-reconnect.
    """
    if _nats_client is None or not _nats_client.is_connected:
        logger.warning("[CHIT] NATS not available — invalidation subscriber exiting")
        return

    topic = settings.chit_cache_invalidate_topic
    logger.info("[CHIT] Subscribing to topic: %s", topic)

    try:
        async def _handle_invalidation(msg: Any) -> None:
            """Process a single cache invalidation message."""
            try:
                data = json.loads(msg.data.decode("utf-8"))
                action = data.get("action", "unknown")
                scope = data.get("scope", "all")
                query_hash = data.get("query_hash", "unknown")

                cache_invalidations_total.labels(scope=scope).inc()
                logger.info(
                    "[CHIT] Invalidation received: action=%s scope=%s query_hash=%s",
                    action,
                    scope,
                    query_hash,
                )

                if scope in ("layer1", "all"):
                    try:
                        await cache.invalidate(query_hash)
                        logger.debug("[CHIT] Layer 1 invalidation OK: %s", query_hash)
                    except Exception as exc:
                        logger.warning("[CHIT] Layer 1 invalidation failed: %s", exc)

                if scope in ("layer0", "all") and cipher.enabled:
                    try:
                        await cipher.invalidate(query_hash)
                        logger.debug("[CHIT] Layer 0 invalidation OK: %s", query_hash)
                    except Exception as exc:
                        logger.warning("[CHIT] Layer 0 invalidation failed: %s", exc)

            except json.JSONDecodeError as exc:
                logger.warning("[CHIT] Invalid JSON in invalidation message: %s", exc)
            except Exception as exc:
                logger.error("[CHIT] Error processing invalidation: %s", exc)

        sub = await _nats_client.subscribe(topic, cb=_handle_invalidation)
        logger.info("[CHIT] Subscription active on topic: %s (sid=%s)", topic, sub.sid)

        # Keep the subscription alive until the NATS connection closes
        while _nats_client.is_connected:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("[CHIT] Invalidation subscriber cancelled")
    except Exception as exc:
        logger.error("[CHIT] Invalidation subscriber error: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
# Request forwarding helpers
# ═══════════════════════════════════════════════════════════════════════════

async def _forward_passthrough(
    body: dict[str, Any],
    path: str | None = None,
    request_id: str | None = None,
) -> Response:
    """
    Forward request to TensorZero without caching.

    Used for: non-cacheable requests, embedding failures, and
    requests that don't meet the cacheability filter.
    """
    rid = request_id or _generate_request_id()
    target = f"{settings.tensorzero_url}{path or '/openai/v1/chat/completions'}"

    t0 = time.monotonic()
    try:
        resp = await http_client.post(target, json=body)
        tensorzero_forward_duration.labels(cached="false").observe(time.monotonic() - t0)
        logger.debug(
            "[%s] Passthrough to TensorZero: status=%d duration=%.4f",
            rid,
            resp.status_code,
            time.monotonic() - t0,
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type="application/json",
            headers=dict(resp.headers),
        )
    except httpx.TimeoutException as exc:
        tensorzero_forward_errors_total.labels(error_type="timeout").inc()
        logger.error("[%s] TensorZero timeout: %s", rid, exc)
        return JSONResponse(
            status_code=504,
            content={
                "error": {
                    "message": "Gateway timeout",
                    "type": "proxy_error",
                    "code": "tensorzero_timeout",
                }
            },
        )
    except httpx.HTTPError:
        tensorzero_forward_errors_total.labels(error_type="http_error").inc()
        logger.exception("[%s] TensorZero HTTP error", rid)
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": "Bad gateway",
                    "type": "proxy_error",
                    "code": "tensorzero_http_error",
                }
            },
        )
    except Exception:
        tensorzero_forward_errors_total.labels(error_type="unknown").inc()
        logger.exception("[%s] TensorZero forward failed", rid)
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": "Service unavailable",
                    "type": "proxy_error",
                    "code": "tensorzero_unavailable",
                }
            },
        )


async def _forward_and_capture(
    body: dict[str, Any],
    request_id: str | None = None,
) -> httpx.Response | None:
    """
    Forward to TensorZero and return the raw response for caching.

    Returns *None* on any failure so the caller can handle the
    fallback response construction.  This is the fail-open path.
    """
    rid = request_id or _generate_request_id()
    t0 = time.monotonic()

    try:
        resp = await http_client.post(
            f"{settings.tensorzero_url}/openai/v1/chat/completions",
            json=body,
        )
        tensorzero_forward_duration.labels(cached="false").observe(time.monotonic() - t0)
        logger.debug(
            "[%s] Forward-and-capture: status=%d duration=%.4f",
            rid,
            resp.status_code,
            time.monotonic() - t0,
        )
        return resp
    except Exception as exc:
        tensorzero_forward_errors_total.labels(error_type="capture_failed").inc()
        logger.error("[%s] TensorZero forward-and-capture failed: %s", rid, exc)
        return None


async def _forward_streaming(
    body: dict[str, Any],
    request_id: str | None = None,
) -> StreamingResponse:
    """
    Forward a streaming (SSE) request to TensorZero and stream the
    response back to the client.

    Streaming responses are never cached — the SSE chunks are forwarded
    as they arrive to minimise time-to-first-token (TTFT).
    """
    rid = request_id or _generate_request_id()
    target = f"{settings.tensorzero_url}/openai/v1/chat/completions"

    logger.debug("[%s] Streaming forward to: %s", rid, target)

    async def _stream_generator():
        """Async generator that yields SSE chunks from TensorZero."""
        try:
            async with http_client.stream("POST", target, json=body) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk
        except httpx.TimeoutException as exc:
            tensorzero_forward_errors_total.labels(error_type="stream_timeout").inc()
            logger.error("[%s] Streaming timeout: %s", rid, exc)
            yield b"data: [ERROR] Stream timeout\\n\\n"
        except Exception as exc:
            tensorzero_forward_errors_total.labels(error_type="stream_error").inc()
            logger.error("[%s] Streaming error: %s", rid, exc)
            yield b"data: [ERROR] Stream interrupted\\n\\n"

    return StreamingResponse(
        _stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# Response construction helpers
# ═══════════════════════════════════════════════════════════════════════════


def _build_cached_response(
    cached: dict[str, Any],
    original_body: dict[str, Any],
    request_id: str | None = None,
) -> JSONResponse:
    """
    Build an OpenAI-compatible response from cached data.

    Injects cache metadata headers so upstream clients can observe
    that a cached response was served.
    """
    rid = request_id or _generate_request_id()

    try:
        content = json.loads(cached["response_text"])
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("[%s] Failed to parse cached response: %s", rid, exc)
        # Fail-open: return a minimal error response
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": "Cached response corrupted",
                    "type": "cache_error",
                    "code": "cache_decode_error",
                }
            },
        )

    # Inject cache metadata into response headers
    headers: dict[str, str] = {
        "X-Cache": "HIT",
        "X-Cache-Id": str(cached.get("id", "unknown")),
        "X-Cache-Similarity": str(cached.get("similarity_score", 0.0)),
        "X-Cache-Model": original_body.get("model", "unknown"),
        "X-Cache-Layer": cached.get("layer", "unknown"),
        "X-Request-Id": rid,
    }

    logger.debug("[%s] Built cached response: %s", rid, headers)
    return JSONResponse(content=content, headers=headers)


# ═══════════════════════════════════════════════════════════════════════════
# Cacheability filter
# ═══════════════════════════════════════════════════════════════════════════


def _is_cacheable(body: dict[str, Any]) -> bool:
    """
    Determine whether a chat completion request is eligible for caching.

    Criteria:
        - ≤ 3 messages (short conversational context)
        - No tool/function calling (non-deterministic expansions)
        - Temperature ≤ configurable threshold (deterministic-ish)
        - At least one user message present
    """
    messages = body.get("messages", [])
    if len(messages) > 3:
        logger.debug("Not cacheable: %d messages > 3", len(messages))
        return False
    if body.get("tools") or body.get("functions"):
        logger.debug("Not cacheable: tools/functions present")
        return False
    if body.get("temperature", 0.0) > settings.max_cacheable_temperature:
        logger.debug(
            "Not cacheable: temperature=%.2f > threshold=%.2f",
            body.get("temperature", 0.0),
            settings.max_cacheable_temperature,
        )
        return False
    if not any(m.get("role") == "user" for m in messages):
        logger.debug("Not cacheable: no user message found")
        return False
    return True


def _extract_query_text(body: dict[str, Any]) -> str:
    """
    Extract the last user message as the query text for embedding.

    Handles:
        - Plain string content
        - Multi-modal content (list of {type, text/image_url} objects)
    """
    for msg in reversed(body.get("messages", [])):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                # Multi-modal: extract text parts, join with spaces
                text_parts = [
                    p.get("text", "")
                    for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                return " ".join(text_parts).strip()
            if isinstance(content, str):
                return content.strip()
            return ""
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# Utility helpers
# ═══════════════════════════════════════════════════════════════════════════


def _generate_request_id() -> str:
    """
    Generate a short, unique request ID for log correlation.

    Uses a truncated SHA-256 hash of the current time to avoid
dependencies on external ID generators.
    """
    return hashlib.sha256(str(time.monotonic()).encode()).hexdigest()[:12]
