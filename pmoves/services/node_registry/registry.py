"""Node Registry service for P2P compute coordination.

Receives node announcements via NATS, tracks capabilities, and provides
query interface for work allocator to find suitable nodes.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .storage import InMemoryNodeStore, NodeRecord, SupabaseNodeStore, naive_utc
from ..resource_detector.hardware import CpuInfo, GpuInfo, NodeTier, SystemMemory
from ..resource_detector.models import NodeCapabilities

logger = logging.getLogger(__name__)


# NATS subjects for node registry.
#
# WHY THESE STRINGS (D4 / PRE_RESTART_PREFLIGHT R8): the registry used to
# subscribe to `compute.nodes.announce.v1` while every publisher in the repo
# announces on `mesh.node.announce.v1` -- mesh-agent (the DEPLOYED publisher:
# it has a Dockerfile and a compose entry), pmoves/scripts/bootstrap-node.sh
# and pmoves/scripts/mesh-bind.sh. Two finished halves wired to different
# strings: the announcements reached nobody and the registry heard nothing.
#
# The SUBSCRIBER moved, not the publisher. `mesh.node.announce.v1` is the
# subject declared across pmoves/config/agent_registry.yaml,
# pmoves/services/graphiti/nats_subject_registry.py and the bootstrap
# scripts, and mesh-agent additionally publishes the richer v2 payload
# (namespace identity + topology), which this registry also consumes.
SUBJECTS = {
    "announce": "mesh.node.announce.v1",
    "announce_v2": "mesh.node.announce.v2",
    # Both versions live in one subject family; the JetStream consumer takes
    # the whole family in one durable subscription.
    "announce_family": "mesh.node.announce.>",
    # There is NO separate heartbeat subject, and there is no second
    # subscription for one (F3). The mesh re-announces every ANNOUNCE_SEC
    # seconds, so the announcement IS the heartbeat: the announce-family
    # subscription already delivers every v1 message, and the handler
    # refreshes `last_heartbeat` through `storage.register()`. A second
    # subscription on the SAME subject was a duplicate delivery of every
    # announcement, and it was the only thing keeping a "heartbeat" subject
    # alive in this table.
    "query": "compute.nodes.query.v1",
    "response": "compute.nodes.response.v1",
    "drain": "compute.nodes.drain.v1",
}

# JetStream stream that carries the announce family (see
# pmoves/scripts/nats/init_streams.sh -- the COMPUTE stream).
#
# WHY UPPERCASE (F2): the stream's NAME is `COMPUTE` -- that is the literal
# string `add_stream COMPUTE` creates, and JetStream stream names are
# case-sensitive. `stream="compute"` asked for a stream that did not exist,
# so every subscribe attempt failed and the registry silently fell back to
# core NATS. The name must be byte-for-byte the name init_streams.sh
# creates, and the validator expects.
ANNOUNCE_STREAM = "COMPUTE"
ANNOUNCE_DURABLE = "node-registry-announce"


def _first_str(payload: Dict[str, Any], *keys: str) -> Optional[str]:
    """First non-empty string value among *keys*, or None."""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def node_id_from_announcement(payload: Dict[str, Any]) -> Optional[str]:
    """Node id from any announcement dialect published in this repo.

    * mesh-agent v1/v2 -> {"node": <hostname>, "slug": <id>}
    * bootstrap-node.sh / mesh-bind.sh -> {"node_id": <id>}
    * the registry's own protocol -> {"node_id": <id>}
    """
    return _first_str(payload, "node_id", "slug", "node")


def timestamp_from_announcement(payload: Dict[str, Any]) -> datetime:
    """Announcement timestamp, in the store's naive-UTC convention.

    mesh-agent and the bootstrap scripts send an integer epoch under "ts";
    the registry's own protocol sends an ISO-8601 string under "timestamp".

    WHY THE NORMALISATION (F4): `datetime.fromisoformat` on a string that
    carries an offset ("2026-10-31T00:44:05+00:00", or the "Z" form the
    bootstrap scripts send) returns an AWARE datetime. The store's clock is
    naive, so `now - aware` raises TypeError and the node record could not
    be evaluated at all. Every value that enters the store is converted to
    UTC and stripped of its tzinfo.
    """
    raw = payload.get("timestamp")
    if isinstance(raw, str):
        try:
            return naive_utc(datetime.fromisoformat(raw.replace("Z", "+00:00")))
        except ValueError:
            pass
    epoch = payload.get("ts")
    if isinstance(epoch, (int, float)):
        return naive_utc(datetime.fromtimestamp(epoch))
    return datetime.now()


def _tier_from_announcement(payload: Dict[str, Any]) -> NodeTier:
    """Node tier from an announcement, defaulting when it says nothing.

    WHY (D4): mesh-agent v2 announces its namespace tier
    (`namespace.tier`, from SERVICE_TIER); the v1 payload and the bootstrap
    scripts say nothing about the tier at all. An announcement with no
    hardware facts is registered as CPU_PEER -- the least GPU-capable tier
    that still describes an online node -- with ZERO available slots, so the
    work allocator cannot route work to a node that never claimed any
    capacity until a hardware probe reports real numbers.
    """
    candidates = [
        _first_str(payload, "tier"),
        _first_str(payload.get("namespace") or {}, "tier"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return NodeTier(candidate)
        except ValueError:
            continue
    return NodeTier.CPU_PEER


def capabilities_from_announcement(payload: Dict[str, Any]) -> NodeCapabilities:
    """Build a NodeCapabilities record from a mesh announcement.

    WHY (D4): the registry used to hand every announcement to
    NodeCapabilities.from_nats_message(), which expects the registry's OWN
    full capability message ({node_id, hostname, tier, cpu_cores, ...}). The
    messages that actually flow on mesh.node.announce.v1/v2 are presence
    announcements with no hardware facts, so every single one raised
    KeyError('node_id') and was dropped -- the registry stayed empty even
    once the subject matched.

    This maps each dialect (mesh-agent v1, mesh-agent v2, the bootstrap
    scripts) onto the capability record. Hardware facts are never invented:
    an announcement without them yields zero capacity.
    """
    node_id = node_id_from_announcement(payload)
    if not node_id:
        raise ValueError("announcement carries no node identity")

    hostname = _first_str(payload, "hostname", "node") or node_id

    memory_mb = int(payload.get("memory_mb", 0) or 0)
    memory_gb = float(payload.get("memory_gb", 0.0) or 0.0)
    if not memory_mb and memory_gb:
        memory_mb = int(memory_gb * 1024)
    if not memory_gb and memory_mb:
        memory_gb = memory_mb / 1024

    cpu_threads = int(payload.get("cpu_threads", payload.get("cpu_cores", 0)) or 0)
    cpu_cores = int(payload.get("cpu_cores", 0) or 0)

    gpus = []
    for index, name in enumerate(payload.get("gpu_models", []) or []):
        gpus.append(
            GpuInfo(
                index=index,
                name=name,
                total_vram_mb=0,
                total_vram_gb=0.0,
                driver_version="unknown",
                cuda_version="unknown",
            )
        )

    host = _first_str(payload, "host")
    tailscale_ip = _first_str(payload, "tailscale_ip")

    return NodeCapabilities(
        node_id=node_id,
        hostname=hostname,
        tier=_tier_from_announcement(payload),
        cpu=CpuInfo(
            cores=cpu_cores,
            threads_per_core=1,
            total_threads=cpu_threads,
            model_name=_first_str(payload, "cpu_model", "model_name") or "Unknown",
            mhz_per_cpu=float(payload.get("cpu_mhz", 0.0) or 0.0),
        ),
        memory=SystemMemory(
            total_mb=memory_mb,
            total_gb=memory_gb,
            available_mb=int(payload.get("available_memory_mb", 0) or 0),
            available_gb=float(payload.get("available_memory_mb", 0) or 0) / 1024,
        ),
        gpus=gpus,
        total_gpu_vram_gb=float(payload.get("gpu_vram_gb", 0.0) or 0.0),
        ipv4=tailscale_ip or (host if host and host[0].isdigit() else None),
        ipv6=None,
        port=int(payload.get("port", 4222) or 4222),
        available_cpu_slots=int(payload.get("available_cpu_slots", 0) or 0),
        available_gpu_slots=int(payload.get("available_gpu_slots", 0) or 0),
        available_memory_mb=int(payload.get("available_memory_mb", 0) or 0),
        available_vram_mb=int(payload.get("available_vram_mb", 0) or 0),
        supported_models=list(payload.get("supported_models", []) or []),
        supported_frameworks=list(payload.get("supported_frameworks", []) or []),
        is_online=True,
        is_draining=False,
        last_heartbeat=timestamp_from_announcement(payload),
        uptime_seconds=float(payload.get("uptime_seconds", 0.0) or 0.0),
    )



class NodeRegistry:
    """NATS-based node registry service.

    Listens for node announcements and heartbeats, maintains node
    capability catalog, and responds to queries from work allocator.
    """

    def __init__(
        self,
        nats_url: str = "nats://nats:4222",
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

        # Unsubscribe and close NATS. `self._subscriptions` holds the
        # JetStream announce subscription AND every core-NATS fallback, so
        # both paths are torn down here.
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception:
                pass

        if self._nc:
            await self._nc.close()

        logger.info("Node registry stopped")

    async def _subscribe_announce(self):
        """Subscribe to node announcements (mesh.node.announce.v1 AND .v2).

        WHY (D4): mesh-agent publishes BOTH versions of the announcement --
        v1 for backward compatibility and v2 with namespace identity and
        topology. The registry must consume both, otherwise it ignores half
        of what the mesh says about itself.
        """

        async def on_announce(msg):
            try:
                payload = json.loads(msg.data.decode())
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(f"Invalid announcement message format: {e}", exc_info=True)
                return
            except Exception as e:
                logger.error(f"Error processing announcement: {e}", exc_info=True)
                return

            try:
                capabilities = capabilities_from_announcement(payload)
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Invalid announcement payload: {e}", exc_info=True)
                return

            try:
                await self.storage.register(capabilities)
                logger.debug(
                    f"Node announcement: {capabilities.node_id} ({capabilities.tier.value})"
                )
            except Exception as e:
                logger.error(f"Error processing announcement: {e}", exc_info=True)

        # JetStream first: the announce family is durable, so a registry that
        # restarts catches up on the announcements it missed instead of
        # waiting for the next 15s cycle.
        try:
            js_sub = await self._js.subscribe(
                subject=SUBJECTS["announce_family"],
                stream=ANNOUNCE_STREAM,
                durable=ANNOUNCE_DURABLE,
                cb=on_announce,
            )
            # The JetStream subscription is tracked like every other one, so
            # stop() tears it down too. Without this the subscription leaked
            # on every restart and the durable consumer kept a live
            # interest on the stream.
            self._subscriptions.append(js_sub)
            logger.info(
                f"Subscribed to {SUBJECTS['announce_family']} "
                f"(JetStream stream {ANNOUNCE_STREAM})"
            )
        except Exception:
            # Fallback to regular subscriptions -- one per published version.
            for subject in (SUBJECTS["announce"], SUBJECTS["announce_v2"]):
                sub = await self._nc.subscribe(subject, cb=on_announce)
                self._subscriptions.append(sub)
                logger.info(f"Subscribed to {subject} (non-JetStream)")

    async def _subscribe_query(self):
        """Subscribe to node queries."""

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
                payload = json.loads(msg.data.decode())
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
    nats_url: str = "nats://nats:4222",
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
    nats_url: str = "nats://nats:4222",
    api_host: str = "0.0.0.0",
    api_port: int = 8115,
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

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    nats_url = os.environ.get("NATS_URL", "nats://nats:4222")
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

    try:
        asyncio.run(run_registry(nats_url, supabase_url, supabase_key))
    except KeyboardInterrupt:
        logger.info("Registry stopped by user")
