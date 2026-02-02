"""HTTP API for Node Registry service.

Provides REST endpoints for node registration, heartbeat, and querying.
Complements the NATS-based message bus with direct HTTP access.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .registry import NodeRegistry, SUBJECTS
from ..resource_detector.models import NodeCapabilities, NodeHeartbeat

logger = logging.getLogger(__name__)


class NodeRegistryAPI:
    """HTTP API wrapper for NodeRegistry.

    Provides REST endpoints for:
    - POST /register - Register a node
    - POST /heartbeat - Send heartbeat
    - GET /nodes - List nodes
    - GET /nodes/{node_id} - Get node details
    - POST /nodes/{node_id}/drain - Drain a node
    - GET /stats - Registry statistics
    """

    def __init__(
        self,
        registry: NodeRegistry,
        host: str = "0.0.0.0",
        port: int = 8082,
    ):
        """Initialize API server.

        Args:
            registry: NodeRegistry instance
            host: Host to bind to
            port: Port to listen on
        """
        self.registry = registry
        self.host = host
        self.port = port
        self._server: Optional[Any] = None
        self._runner: Optional[Any] = None
        self._site: Optional[Any] = None

    async def start(self):
        """Start the HTTP API server."""
        try:
            from aiohttp import web
        except ImportError:
            logger.error("aiohttp not installed, cannot start HTTP API")
            return

        app = web.Application()
        self._setup_routes(app)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        logger.info(f"NodeRegistry API started on http://{self.host}:{self.port}")

    async def stop(self):
        """Stop the HTTP API server."""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        logger.info("NodeRegistry API stopped")

    def _setup_routes(self, app):
        """Setup HTTP routes."""
        from aiohttp import web

        # Node registration
        app.add_post("/register", self._handle_register)
        app.add_post("/heartbeat", self._handle_heartbeat)

        # Node queries
        app.add_get("/nodes", self._handle_list_nodes)
        app.add_get("/nodes/{node_id}", self._handle_get_node)

        # Node management
        app.add_post("/nodes/{node_id}/drain", self._handle_drain_node)
        app.add_post("/nodes/{node_id}/undrain", self._handle_undrain_node)

        # Registry stats
        app.add_get("/stats", self._handle_stats)
        app.add_get("/healthz", self._handle_healthz)

        # Work allocation queries
        app.add_post("/query", self._handle_query)

    async def _handle_register(self, request):
        """Handle node registration.

        Expected JSON body:
        {
            "node_id": "string",
            "hostname": "string",
            "tier": "string",
            "cpu_cores": int,
            "total_cpu_slots": int,
            "available_cpu_slots": int,
            "total_memory_mb": int,
            "available_memory_mb": int,
            "gpus": [...],
            "total_gpu_vram_mb": int,
            "ipv4": "string",
            ...
        }
        """
        from aiohttp import web

        try:
            payload = await request.json()

            # Validate required fields
            required = ["node_id", "hostname", "tier"]
            missing = [f for f in required if f not in payload]
            if missing:
                return web.json_response(
                    {"error": f"Missing required fields: {missing}"},
                    status=400,
                )

            # Create NodeCapabilities from payload
            capabilities = NodeCapabilities.from_dict(payload)

            # Register with storage backend
            record = await self.registry.storage.register(capabilities)

            logger.info(f"Node registered via HTTP: {capabilities.node_id}")

            return web.json_response({
                "status": "registered",
                "node_id": capabilities.node_id,
                "registered_at": record.registered_at.isoformat(),
                "tier": capabilities.tier.value,
            })

        except (ValueError, KeyError) as e:
            logger.warning(f"Invalid payload for node registration: {e}")
            return web.json_response(
                {"error": "Invalid payload format", "detail": "node_id, hostname, and tier are required"},
                status=400,
            )
        except Exception as e:
            logger.error(f"Error in register endpoint: {e}", exc_info=True)
            return web.json_response(
                {"error": "Registration failed", "error_id": "NODE_REGISTRY_001"},
                status=500,
            )

    async def _handle_heartbeat(self, request):
        """Handle node heartbeat.

        Expected JSON body:
        {
            "node_id": "string",
            "timestamp": "ISO datetime",
            "cpu_utilization": float,
            "memory_utilization": float,
            "gpu_utilization": [float, ...],
            "active_jobs": int,
            "status": "online" | "busy" | "draining"
        }
        """
        from aiohttp import web

        try:
            payload = await request.json()

            if "node_id" not in payload:
                return web.json_response(
                    {"error": "Missing node_id"},
                    status=400,
                )

            # Create NodeHeartbeat from payload
            heartbeat = NodeHeartbeat(
                node_id=payload["node_id"],
                timestamp=datetime.fromisoformat(
                    payload.get("timestamp", datetime.now().isoformat())
                ),
                cpu_utilization=payload.get("cpu_utilization", 0.0),
                memory_utilization=payload.get("memory_utilization", 0.0),
                gpu_utilization=payload.get("gpu_utilization", []),
                active_jobs=payload.get("active_jobs", 0),
                status=payload.get("status", "online"),
            )

            await self.registry.storage.update_heartbeat(heartbeat)

            return web.json_response({
                "status": "received",
                "node_id": heartbeat.node_id,
            })

        except (ValueError, KeyError) as e:
            logger.warning(f"Invalid heartbeat payload: {e}")
            return web.json_response(
                {"error": "Invalid payload format", "detail": "node_id is required"},
                status=400,
            )
        except Exception as e:
            logger.error(f"Error in heartbeat endpoint: {e}", exc_info=True)
            return web.json_response(
                {"error": "Heartbeat failed", "error_id": "NODE_REGISTRY_002"},
                status=500,
            )

    async def _handle_list_nodes(self, request):
        """Handle list nodes request.

        Query params:
            - tier: Filter by tier
            - online_only: Only online nodes (default true)
            - status: Filter by status (online, busy, draining)
        """
        from aiohttp import web

        try:
            tier = request.query.get("tier")
            online_only = request.query.get("online_only", "true").lower() == "true"
            status = request.query.get("status")

            # Get nodes from storage
            if tier:
                records = await self.registry.storage.list_by_tier(tier)
            elif online_only:
                records = await self.registry.storage.list_online()
            else:
                records = await self.registry.storage.list_all()

            # Filter by status if specified
            if status:
                records = [r for r in records if r.status == status]

            # Convert to response format
            nodes = [
                {
                    "node_id": r.capabilities.node_id,
                    "hostname": r.capabilities.hostname,
                    "tier": r.capabilities.tier.value,
                    "status": r.status,
                    "cpu_cores": r.capabilities.cpu_cores,
                    "available_cpu_slots": r.capabilities.available_cpu_slots,
                    "available_memory_mb": r.capabilities.available_memory_mb,
                    "gpu_count": len(r.capabilities.gpus),
                    "total_gpu_vram_mb": r.capabilities.total_gpu_vram_mb,
                    "last_heartbeat": r.last_heartbeat.isoformat() if r.last_heartbeat else None,
                    "utilization_score": r.capabilities.utilization_score,
                }
                for r in records
            ]

            return web.json_response({
                "nodes": nodes,
                "count": len(nodes),
                "timestamp": datetime.now().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error in list_nodes endpoint: {e}")
            return web.json_response(
                {"error": str(e)},
                status=500,
            )

    async def _handle_get_node(self, request):
        """Handle get node details request.

        Path params:
            - node_id: Node identifier
        """
        from aiohttp import web

        try:
            node_id = request.match_info["node_id"]
            record = await self.registry.get_node(node_id)

            if not record:
                return web.json_response(
                    {"error": f"Node {node_id} not found"},
                    status=404,
                )

            return web.json_response({
                "node_id": record.capabilities.node_id,
                "hostname": record.capabilities.hostname,
                "tier": record.capabilities.tier.value,
                "status": record.status,
                "registered_at": record.registered_at.isoformat(),
                "last_heartbeat": record.last_heartbeat.isoformat() if record.last_heartbeat else None,
                "capabilities": record.capabilities.to_dict(),
            })

        except Exception as e:
            logger.error(f"Error in get_node endpoint: {e}")
            return web.json_response(
                {"error": str(e)},
                status=500,
            )

    async def _handle_drain_node(self, request):
        """Handle drain node request.

        Path params:
            - node_id: Node identifier
        """
        from aiohttp import web

        try:
            node_id = request.match_info["node_id"]
            record = await self.registry.get_node(node_id)

            if not record:
                return web.json_response(
                    {"error": f"Node {node_id} not found"},
                    status=404,
                )

            record.status = "draining"
            logger.info(f"Node {node_id} marked as draining via HTTP")

            return web.json_response({
                "status": "draining",
                "node_id": node_id,
            })

        except Exception as e:
            logger.error(f"Error in drain endpoint: {e}")
            return web.json_response(
                {"error": str(e)},
                status=500,
            )

    async def _handle_undrain_node(self, request):
        """Handle undrain node request.

        Path params:
            - node_id: Node identifier
        """
        from aiohttp import web

        try:
            node_id = request.match_info["node_id"]
            record = await self.registry.get_node(node_id)

            if not record:
                return web.json_response(
                    {"error": f"Node {node_id} not found"},
                    status=404,
                )

            # Only allow undrain if not actually busy
            if record.status != "draining":
                return web.json_response(
                    {"error": f"Node {node_id} is not in draining state"},
                    status=400,
                )

            record.status = "online"
            logger.info(f"Node {node_id} marked as online via HTTP")

            return web.json_response({
                "status": "online",
                "node_id": node_id,
            })

        except Exception as e:
            logger.error(f"Error in undrain endpoint: {e}")
            return web.json_response(
                {"error": str(e)},
                status=500,
            )

    async def _handle_stats(self, request):
        """Handle registry stats request."""
        from aiohttp import web

        try:
            stats = self.registry.get_stats()

            return web.json_response({
                **stats,
                "timestamp": datetime.now().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error in stats endpoint: {e}")
            return web.json_response(
                {"error": str(e)},
                status=500,
            )

    async def _handle_healthz(self, request):
        """Handle health check request.

        Checks:
        - NATS connection status
        - Storage backend availability
        - Service running state
        """
        from aiohttp import web

        # Check service state
        is_running = self.registry._running

        # Check NATS connection
        nats_connected = self.registry._nc is not None
        if self.registry._nc:
            try:
                # Try to get current status
                nats_status = self.registry._nc.status
                nats_connected = nats_status.connected
            except Exception:
                nats_connected = False

        # Check storage backend
        storage_healthy = True
        try:
            # For Supabase, check if initialized
            if hasattr(self.registry.storage, "_initialized"):
                storage_healthy = self.registry.storage._initialized
            # For in-memory, just check we can access it
            else:
                self.registry.storage.get_stats()
        except Exception:
            storage_healthy = False

        # Overall health
        is_healthy = is_running and nats_connected and storage_healthy

        status_code = 200 if is_healthy else 503

        return web.json_response({
            "status": "healthy" if is_healthy else "unhealthy",
            "service": "node-registry",
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "running": is_running,
                "nats_connected": nats_connected,
                "storage_healthy": storage_healthy,
            },
        }, status=status_code)

    async def _handle_query(self, request):
        """Handle node query request.

        Expected JSON body:
        {
            "tier": "string (optional)",
            "min_cpu": int (optional),
            "min_ram_mb": int (optional),
            "requires_gpu": bool (default false),
            "online_only": bool (default true)
        }
        """
        from aiohttp import web

        try:
            payload = await request.json() if request.content_length else {}

            tier = payload.get("tier")
            min_cpu = payload.get("min_cpu")
            min_ram_mb = payload.get("min_ram_mb")
            requires_gpu = payload.get("requires_gpu", False)
            online_only = payload.get("online_only", True)

            records = await self.registry.storage.query(
                tier=tier,
                min_cpu=min_cpu,
                min_ram_mb=min_ram_mb,
                requires_gpu=requires_gpu,
                online_only=online_only,
            )

            # Sort by utilization score
            records.sort(key=lambda r: r.capabilities.utilization_score)

            nodes = [
                {
                    "node_id": r.capabilities.node_id,
                    "hostname": r.capabilities.hostname,
                    "tier": r.capabilities.tier.value,
                    "utilization_score": r.capabilities.utilization_score,
                    "available_cpu_slots": r.capabilities.available_cpu_slots,
                    "available_memory_mb": r.capabilities.available_memory_mb,
                }
                for r in records
            ]

            return web.json_response({
                "nodes": nodes,
                "count": len(nodes),
                "timestamp": datetime.now().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error in query endpoint: {e}")
            return web.json_response(
                {"error": str(e)},
                status=500,
            )


async def run_api_server(
    registry: NodeRegistry,
    host: str = "0.0.0.0",
    port: int = 8082,
):
    """Run the HTTP API server.

    Args:
        registry: NodeRegistry instance
        host: Host to bind to
        port: Port to listen on
    """
    api = NodeRegistryAPI(registry, host, port)
    await api.start()

    try:
        # Keep running
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await api.stop()
