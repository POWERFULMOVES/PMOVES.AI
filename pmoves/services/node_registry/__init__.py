"""Node Registry Service - P2P compute coordination.

This service maintains a catalog of distributed compute nodes,
tracking their capabilities via NATS announcements and heartbeats.

The package directory used to be kebab-case (`node-registry`), which made
`pmoves.services.node_registry` unimportable -- the relative imports inside
the service (`from ..resource_detector.models import ...`) could never
resolve when the modules were loaded by file path. The directory is now
`node_registry`, so the import below is true.

Usage:
    from pmoves.services.node_registry import NodeRegistry, run_registry, run_with_api

    # Run with both NATS and HTTP API
    await run_with_api(
        nats_url="nats://nats:4222",
        api_host="0.0.0.0",
        api_port=8082,
    )

    # Or use components separately
    registry = NodeRegistry(nats_url="nats://nats:4222")
    await registry.start()

NATS Subjects:
    - mesh.node.announce.v1: Node presence announcements (mesh-agent)
    - mesh.node.announce.v2: Node announcements with namespace + topology
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
