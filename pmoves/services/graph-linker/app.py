"""Graph Linker -- FastAPI service for persisting entity relationships to Neo4j.

Subscribes to NATS subjects and executes Cypher queries against Neo4j to store
entity relationships for the PMOVES.AI knowledge graph.

Ports:
    8090: HTTP REST API (health, ready, metrics)

NATS Subjects:
    gen.image.result.v1
    analysis.extract_topics.result.v1
    kb.upsert.request.v1
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import logging
import structlog
from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from config import Settings, get_settings
from models import HealthResponse, ReadyResponse
from nats_handler import NATSHandler
from neo4j_client import Neo4jClient

logger = structlog.get_logger(__name__)

# -- Prometheus metrics ---------------------------------------------------

MESSAGES_RECEIVED = Counter(
    "graph_linker_messages_received_total",
    "Total NATS messages received",
    ["subject"],
)
MESSAGES_PROCESSED = Counter(
    "graph_linker_messages_processed_total",
    "Total NATS messages successfully processed",
    ["subject"],
)
MESSAGES_FAILED = Counter(
    "graph_linker_messages_failed_total",
    "Total NATS messages that failed processing",
    ["subject"],
)
DEAD_LETTERED = Counter(
    "graph_linker_dead_lettered_total",
    "Total messages published to dead-letter",
)
NEO4J_QUERY_DURATION = Histogram(
    "graph_linker_neo4j_query_duration_seconds",
    "Neo4j query execution duration",
    ["operation"],
)

# -- Application state ----------------------------------------------------

_neo4j_client: Neo4jClient | None = None
_nats_handler: NATSHandler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """""""""Application lifespan -- startup and shutdown."""""""""
    global _neo4j_client, _nats_handler

    settings = get_settings()
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
    )

    logger.info("graph_linker.starting", version="0.2.0")

    # Initialize Neo4j
    _neo4j_client = Neo4jClient(settings)
    await _neo4j_client.connect()
    _neo4j_client.apply_migrations()

    # Initialize NATS handler
    _nats_handler = NATSHandler(settings, _neo4j_client)

    # NATS connection is best-effort
    try:
        await _nats_handler.connect()
        await _nats_handler.subscribe()
        logger.info("graph_linker.nats_ready")
    except Exception as exc:
        logger.warning(
            "graph_linker.nats_unavailable",
            error=str(exc),
            hint="Service will continue but will not process NATS messages",
        )

    logger.info("graph_linker.started", port=settings.port)
    yield

    # Shutdown
    logger.info("graph_linker.stopping")
    if _nats_handler:
        await _nats_handler.close()
    if _neo4j_client:
        await _neo4j_client.close()
    logger.info("graph_linker.stopped")


# -- FastAPI app -----------------------------------------------------------

app = FastAPI(
    title="PMOVES-Graph-Linker",
    description="NATS-to-Neo4j entity relationship persistence service",
    version="0.2.0",
    lifespan=lifespan,
)


# -- Health endpoints ------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """""""""Liveness check -- always returns OK if the process is running."""""""""
    return HealthResponse()


@app.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    """""""""Readiness check -- verifies Neo4j and NATS connectivity."""""""""
    neo4j_status = "ok" if _neo4j_client and _neo4j_client.is_healthy() else "unavailable"
    nats_status = "ok" if _nats_handler and _nats_handler.is_connected else "unavailable"
    overall = "ready" if neo4j_status == "ok" else "degraded"
    return ReadyResponse(
        status=overall,
        neo4j=neo4j_status,
        nats=nats_status,
    )


# -- Metrics endpoint ------------------------------------------------------

@app.get("/metrics")
async def metrics() -> Response:
    """""""""Prometheus metrics endpoint."""""""""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# -- Entry point -----------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )
