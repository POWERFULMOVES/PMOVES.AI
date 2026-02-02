"""Node Registry Service - P2P compute coordination.

This service maintains a catalog of distributed compute nodes,
tracking their capabilities via NATS announcements and heartbeats.

Usage:
    from pmoves.services.node_registry import NodeRegistry, run_registry, run_with_api

    # Run with both NATS and HTTP API
    await run_with_api(
        nats_url="nats://localhost:4222",
        api_host="0.0.0.0",
        api_port=8082,
    )

    # Or use components separately
    registry = NodeRegistry(nats_url="nats://localhost:4222")
    await registry.start()

NATS Subjects:
    - compute.nodes.announce.v1: Node capability announcements
    - compute.nodes.heartbeat.v1: Node liveness updates
    - compute.nodes.query.v1: Query for available nodes
    - compute.nodes.drain.v1: Request node to drain

HTTP Endpoints (port 8082):
    - POST /register - Register a node
    - POST /heartbeat - Send heartbeat
    - GET /nodes - List nodes
    - GET /nodes/{node_id} - Get node details
    - POST /nodes/{node_id}/drain - Drain a node
    - GET /stats - Registry statistics
    - GET /healthz - Health check
"""

from .registry import NodeRegistry, SUBJECTS, run_registry, run_with_api
from .storage import (
    InMemoryNodeStore,
    SupabaseNodeStore,
    NodeRecord,
    CREATE_TABLE_SQL,
)
from .api import NodeRegistryAPI, run_api_server

__all__ = [
    "NodeRegistry",
    "run_registry",
    "run_with_api",
    "SUBJECTS",
    "InMemoryNodeStore",
    "SupabaseNodeStore",
    "NodeRecord",
    "NodeRegistryAPI",
    "run_api_server",
    "CREATE_TABLE_SQL",
]
