"""Node Registry service for P2P compute coordination.

Receives node announcements via NATS, tracks capabilities, and provides
query interface for work allocator to find suitable nodes.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from .storage import InMemoryNodeStore, NodeRecord, SupabaseNodeStore
from ..resource_detector.models import NodeCapabilities, NodeHeartbeat

logger = logging.getLogger(__name__)


# NATS subjects for node registry
SUBJECTS = {
    "announce": "compute.nodes.announce.v1",
    "heartbeat": "compute.nodes.heartbeat.v1",
    "query": "compute.nodes.query.v1",
    "response": "compute.nodes.response.v1",
    "drain": "compute.nodes.drain.v1",
}


class NodeRegistry:
    """NATS-based node registry service.

    Listens for node announcements and heartbeats, maintains node
    capability catalog, and responds to queries from work allocator.
    """

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        storage: Optional[InMemoryNodeStore] = None,
        stale_threshold_seconds: int = 60,
        cleanup_interval_seconds: int = 300,
    ):
        """Initialize node registry.

        Args:
            nats_url: NATS server URL
            storage: Storage backend (defaults to InMemoryNodeStore)
            stale_threshold_seconds: Seconds before node is considered stale
            cleanup_interval_seconds: Interval between stale node cleanup runs
        """
        self.nats_url = nats_url
        self.storage = storage or InMemoryNodeStore(stale_threshold_seconds)
        self.stale_threshold = stale_threshold_seconds
        self.cleanup_interval = cleanup_interval_seconds

        self._nc: Optional[Any] = None
        self._js: Optional[Any] = None
        self._running = False
        self._subscriptions: List = []
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the registry service.

        Connects to NATS, subscribes to subjects, starts cleanup task.
        """
        if self._running:
            logger.warning("Registry already running")
            return

        try:
            import nats

            self._nc = await nats.connect(self.nats_url)
            self._js = self._nc.jetstream()

            logger.info(f"Connected to NATS at {self.nats_url}")

            # Subscribe to node announcements
            await self._subscribe_announce()

            # Subscribe to heartbeats
            await self._subscribe_heartbeat()

            # Subscribe to queries
            await self._subscribe_query()

            # Subscribe to drain requests
            await self._subscribe_drain()

            # Start cleanup task
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            self._running = True
            logger.info("Node registry started")

        except ImportError:
            logger.error("nats-py not installed, cannot start registry")
            raise
        except Exception as e:
            logger.error(f"Failed to start registry: {e}")
            raise

    async def stop(self):
        """Stop the registry service."""
        if not self._running:
            return

        self._running = False

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Unsubscribe and close NATS
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception:
                pass

        if self._nc:
            await self._nc.close()

        logger.info("Node registry stopped")

    async def _subscribe_announce(self):
        """Subscribe to node announcements."""
        import nats

        async def on_announce(msg):
            try:
                data = msg.data.decode()
                import json

                payload = json.loads(data)
                capabilities = NodeCapabilities.from_nats_message(payload)

                await self.storage.register(capabilities)

                logger.debug(
                    f"Node announcement: {capabilities.node_id} ({capabilities.tier.value})"
                )

            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(f"Invalid announcement message format: {e}", exc_info=True)
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Invalid announcement payload: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error processing announcement: {e}", exc_info=True)

        # Create JetStream consumer for announcements
        try:
            await self._js.subscribe(
                subject=SUBJECTS["announce"],
                stream="compute",
                durable_name="node-registry-announce",
                cb=on_announce,
            )
            logger.info(f"Subscribed to {SUBJECTS['announce']}")
        except Exception as e:
            # Fallback to regular subscription
            sub = await self._nc.subscribe(SUBJECTS["announce"], cb=on_announce)
            self._subscriptions.append(sub)
            logger.info(f"Subscribed to {SUBJECTS['announce']} (non-JetStream)")

    async def _subscribe_heartbeat(self):
        """Subscribe to node heartbeats."""
        import nats

        async def on_heartbeat(msg):
            try:
                data = msg.data.decode()
                import json

                payload = json.loads(data)
                heartbeat = NodeHeartbeat(
                    node_id=payload["node_id"],
                    timestamp=datetime.fromisoformat(payload["timestamp"]),
                    cpu_utilization=payload.get("cpu_utilization", 0.0),
                    memory_utilization=payload.get("memory_utilization", 0.0),
                    gpu_utilization=payload.get("gpu_utilization", []),
                    active_jobs=payload.get("active_jobs", 0),
                    status=payload.get("status", "online"),
                )

                await self.storage.update_heartbeat(heartbeat)

            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(f"Invalid heartbeat message format: {e}", exc_info=True)
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Invalid heartbeat payload: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error processing heartbeat: {e}", exc_info=True)

        # Subscribe to heartbeats (high volume, use regular subscription)
        sub = await self._nc.subscribe(SUBJECTS["heartbeat"], cb=on_heartbeat)
        self._subscriptions.append(sub)
        logger.info(f"Subscribed to {SUBJECTS['heartbeat']}")

    async def _subscribe_query(self):
        """Subscribe to node queries."""
        import nats

        async def on_query(msg):
            # Define error response helper
            async def send_error(reply_subject, query_id, error_msg, error_id="QUERY_ERROR"):
                if reply_subject:
                    error_response = {
                        "query_id": query_id,
                        "error": error_msg,
                        "error_id": error_id,
                        "nodes": [],
                        "count": 0,
                        "timestamp": datetime.now().isoformat(),
                    }
                    await self._nc.publish(reply_subject, json.dumps(error_response).encode())

            payload = None
            query_id = None

            try:
                data = msg.data.decode()
                import json

                payload = json.loads(data)
                query_id = payload.get("query_id")

                # Query parameters
                tier = payload.get("tier")
                min_cpu = payload.get("min_cpu")
                min_ram_mb = payload.get("min_ram_mb")
                requires_gpu = payload.get("requires_gpu", False)
                online_only = payload.get("online_only", True)

                # Execute query
                records = await self.storage.query(
                    tier=tier,
                    min_cpu=min_cpu,
                    min_ram_mb=min_ram_mb,
                    requires_gpu=requires_gpu,
                    online_only=online_only,
                )

                # Convert to response format
                nodes = [r.capabilities.to_nats_message() for r in records]

                response = {
                    "query_id": query_id,
                    "nodes": nodes,
                    "count": len(nodes),
                    "timestamp": datetime.now().isoformat(),
                }

                # Send response
                reply_subject = msg.reply
                if reply_subject:
                    await self._nc.publish(reply_subject, json.dumps(response).encode())

            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(f"Invalid query message format: {e}", exc_info=True)
                if msg.reply:
                    await send_error(msg.reply, query_id, "Invalid message format", "QUERY_FORMAT_ERROR")
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Invalid query payload: {e}", exc_info=True)
                if msg.reply:
                    await send_error(msg.reply, query_id, "Invalid query parameters", "QUERY_PARAM_ERROR")
            except Exception as e:
                logger.error(f"Error processing query: {e}", exc_info=True)
                if msg.reply:
                    await send_error(msg.reply, query_id, "Query processing failed", "QUERY_INTERNAL_ERROR")

        sub = await self._nc.subscribe(SUBJECTS["query"], cb=on_query)
        self._subscriptions.append(sub)
        logger.info(f"Subscribed to {SUBJECTS['query']}")

    async def _subscribe_drain(self):
        """Subscribe to node drain requests."""
        import nats

        async def on_drain(msg):
            try:
                data = msg.data.decode()
                import json

                payload = json.loads(data)
                node_id = payload.get("node_id")

                if not node_id:
                    return

                # Mark node as draining
                record = await self.storage.get(node_id)
                if record:
                    record.status = "draining"
                    logger.info(f"Node {node_id} marked as draining")

            except Exception as e:
                logger.error(f"Error processing drain: {e}")

        sub = await self._nc.subscribe(SUBJECTS["drain"], cb=on_drain)
        self._subscriptions.append(sub)
        logger.info(f"Subscribed to {SUBJECTS['drain']}")

    async def _cleanup_loop(self):
        """Periodic cleanup of stale nodes."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                removed = await self.storage.cleanup_stale()
                if removed > 0:
                    logger.info(f"Cleaned up {removed} stale nodes")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def get_node(self, node_id: str) -> Optional[NodeRecord]:
        """Get node record by ID.

        Args:
            node_id: Node identifier

        Returns:
            NodeRecord if found, None otherwise
        """
        return await self.storage.get(node_id)

    async def list_nodes(
        self,
        tier: Optional[str] = None,
        online_only: bool = True,
    ) -> List[NodeRecord]:
        """List nodes with optional filtering.

        Args:
            tier: Filter by tier
            online_only: Only return online nodes

        Returns:
            List of NodeRecords
        """
        if tier:
            return await self.storage.list_by_tier(tier)
        elif online_only:
            return await self.storage.list_online()
        else:
            return await self.storage.list_all()

    async def find_best_node(
        self,
        required_cpu: int,
        required_ram_mb: int,
        requires_gpu: bool = False,
        min_tier: Optional[str] = None,
    ) -> Optional[NodeRecord]:
        """Find the best available node for a workload.

        Args:
            required_cpu: Required CPU slots
            required_ram_mb: Required RAM in MB
            requires_gpu: Whether GPU is required
            min_tier: Minimum tier required

        Returns:
            Best matching NodeRecord or None
        """
        records = await self.storage.query(
            tier=min_tier,
            min_cpu=required_cpu,
            min_ram_mb=required_ram_mb,
            requires_gpu=requires_gpu,
            online_only=True,
        )

        if not records:
            return None

        # Sort by utilization score (lower is better)
        records.sort(key=lambda r: r.capabilities.utilization_score)

        return records[0]

    def get_stats(self) -> Dict:
        """Get registry statistics.

        Returns:
            Dictionary with stats
        """
        return self.storage.get_stats()


async def run_registry(
    nats_url: str = "nats://localhost:4222",
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
):
    """Run the node registry service.

    Args:
        nats_url: NATS server URL
        supabase_url: Optional Supabase URL for persistent storage
        supabase_key: Optional Supabase service key
    """
    # Configure storage
    if supabase_url and supabase_key:
        storage = SupabaseNodeStore(supabase_url, supabase_key)
        logger.info("Using Supabase storage backend")
    else:
        storage = InMemoryNodeStore()
        logger.info("Using in-memory storage backend")

    # Create and start registry
    registry = NodeRegistry(nats_url=nats_url, storage=storage)

    # Handle shutdown
    async def shutdown():
        logger.info("Shutting down registry...")
        await registry.stop()

    import signal

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    # Start registry
    await registry.start()

    # Keep running
    try:
        while registry._running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await registry.stop()


async def run_with_api(
    nats_url: str = "nats://localhost:4222",
    api_host: str = "0.0.0.0",
    api_port: int = 8082,
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
):
    """Run the node registry with both NATS and HTTP API.

    Args:
        nats_url: NATS server URL
        api_host: API server host
        api_port: API server port
        supabase_url: Optional Supabase URL for persistent storage
        supabase_key: Optional Supabase service key
    """
    # Configure storage
    if supabase_url and supabase_key:
        storage = SupabaseNodeStore(supabase_url, supabase_key)
        logger.info("Using Supabase storage backend")
    else:
        storage = InMemoryNodeStore()
        logger.info("Using in-memory storage backend")

    # Create registry
    registry = NodeRegistry(nats_url=nats_url, storage=storage)

    # Import API module
    from .api import NodeRegistryAPI

    # Create API server
    api = NodeRegistryAPI(registry, api_host, api_port)

    # Handle shutdown
    async def shutdown():
        logger.info("Shutting down registry and API...")
        await api.stop()
        await registry.stop()

    import signal

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    # Start both services
    await registry.start()
    await api.start()

    logger.info("Node Registry running with NATS and HTTP API")

    # Keep running
    try:
        while registry._running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await api.stop()
        await registry.stop()


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    nats_url = os.environ.get("NATS_URL", "nats://localhost:4222")
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

    try:
        asyncio.run(run_registry(nats_url, supabase_url, supabase_key))
    except KeyboardInterrupt:
        logger.info("Registry stopped by user")
