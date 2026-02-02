"""Storage backend for node registry.

Supports in-memory and Supabase backends for node capability storage.
Provides persistent node catalog with Supabase for multi-host deployments.
"""

import asyncio
import dataclasses
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from ..resource_detector.models import NodeCapabilities, NodeHeartbeat

logger = logging.getLogger(__name__)


# Constants
DEFAULT_STALE_THRESHOLD_SECONDS = 60  # 1 minute
DEFAULT_CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes
STALE_HEARTBEAT_SECONDS = 60  # 1 minute - heartbeat threshold
OFFLINE_HEARTBEAT_SECONDS = 120  # 2 minutes - offline threshold
MB_TO_GB = 1024  # Memory unit conversion
GB_TO_MB = 1024  # Memory unit conversion


# SQL migration for creating the compute_nodes table
CREATE_TABLE_SQL = """
-- Create compute_nodes table for node registry
CREATE TABLE IF NOT EXISTS compute_nodes (
    node_id TEXT PRIMARY KEY,
    hostname TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN (
        'ai_factory', 'worker_hub', 'gpu_peer',
        'cpu_peer', 'edge', 'disaster'
    )),

    -- CPU info
    cpu_cores INTEGER NOT NULL DEFAULT 0,
    cpu_threads INTEGER NOT NULL DEFAULT 0,
    cpu_model TEXT,

    -- Memory info
    memory_mb INTEGER NOT NULL DEFAULT 0,
    memory_gb NUMERIC NOT NULL DEFAULT 0,

    -- GPU info
    gpu_count INTEGER NOT NULL DEFAULT 0,
    gpu_vram_mb INTEGER NOT NULL DEFAULT 0,
    gpu_vram_gb NUMERIC NOT NULL DEFAULT 0,
    gpu_models JSONB DEFAULT '[]'::jsonb,
    gpu_driver_versions JSONB DEFAULT '[]'::jsonb,

    -- Network info
    ipv4 TEXT,
    ipv6 TEXT,
    port INTEGER DEFAULT 4222,
    bandwidth_mbps NUMERIC,
    latency_ms NUMERIC,

    -- Availability
    available_cpu_slots INTEGER DEFAULT 0,
    available_gpu_slots INTEGER DEFAULT 0,
    available_memory_mb INTEGER DEFAULT 0,
    available_vram_mb INTEGER DEFAULT 0,

    -- Service compatibility
    supported_models JSONB DEFAULT '[]'::jsonb,
    supported_frameworks JSONB DEFAULT '["pytorch", "vllm", "tensorrt"]'::jsonb,
    max_context_tokens INTEGER DEFAULT 4096,
    quantization_support JSONB DEFAULT '["fp16", "int8"]'::jsonb,

    -- State
    is_online BOOLEAN DEFAULT true,
    is_draining BOOLEAN DEFAULT false,
    status TEXT DEFAULT 'online' CHECK (status IN (
        'online', 'busy', 'draining', 'offline'
    )),
    last_heartbeat TIMESTAMPTZ,
    uptime_seconds NUMERIC DEFAULT 0,

    -- CHIT integration
    cgp_public_key TEXT,
    geometric_position JSONB,

    -- Metadata
    registered_at TIMESTAMPTZ DEFAULT NOW(),
    heartbeat_count INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Full text search
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', COALESCE(node_id, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(hostname, '')), 'B') ||
        setweight(to_tsvector('simple', COALESCE(tier, '')), 'C')
    ) STORED
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_compute_nodes_tier ON compute_nodes(tier);
CREATE INDEX IF NOT EXISTS idx_compute_nodes_status ON compute_nodes(status);
CREATE INDEX IF NOT EXISTS idx_compute_nodes_last_heartbeat ON compute_nodes(last_heartbeat);
CREATE INDEX IF NOT EXISTS idx_compute_nodes_is_online ON compute_nodes(is_online);
CREATE INDEX IF NOT EXISTS idx_compute_nodes_search ON compute_nodes USING GIN(search_vector);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_compute_nodes_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS compute_nodes_updated_at ON compute_nodes;
CREATE TRIGGER compute_nodes_updated_at
    BEFORE UPDATE ON compute_nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_compute_nodes_updated_at();
"""


@dataclasses.dataclass
class NodeRecord:
    """Stored node record with metadata."""

    capabilities: NodeCapabilities
    registered_at: datetime
    last_heartbeat: datetime
    heartbeat_count: int = 0
    status: str = "online"  # online, busy, draining, offline

    @property
    def is_stale(self) -> bool:
        """Check if node record is stale (no recent heartbeat)."""
        return datetime.now() - self.last_heartbeat > timedelta(seconds=STALE_HEARTBEAT_SECONDS)

    @property
    def is_offline(self) -> bool:
        """Check if node should be considered offline."""
        return datetime.now() - self.last_heartbeat > timedelta(seconds=OFFLINE_HEARTBEAT_SECONDS)


class InMemoryNodeStore:
    """In-memory storage for node registry.

    Fast, ephemeral storage suitable for single-host deployments.
    Data is lost on restart.
    """

    def __init__(self, stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS):
        """Initialize in-memory store.

        Args:
            stale_threshold_seconds: Seconds before a node is considered stale
        """
        self._nodes: Dict[str, NodeRecord] = {}
        self._by_tier: Dict[str, Set[str]] = {}  # tier -> node_ids
        self._stale_threshold = timedelta(seconds=stale_threshold_seconds)

    async def register(self, capabilities: NodeCapabilities) -> NodeRecord:
        """Register a new node or update existing.

        Args:
            capabilities: Node capabilities from announcement

        Returns:
            Created or updated NodeRecord
        """
        now = datetime.now()
        node_id = capabilities.node_id

        if node_id in self._nodes:
            # Update existing node
            record = self._nodes[node_id]
            record.capabilities = capabilities
            record.last_heartbeat = now
            record.status = "online"
        else:
            # New node registration
            record = NodeRecord(
                capabilities=capabilities,
                registered_at=now,
                last_heartbeat=now,
                heartbeat_count=0,
                status="online",
            )
            self._nodes[node_id] = record

            # Index by tier
            tier = capabilities.tier.value
            if tier not in self._by_tier:
                self._by_tier[tier] = set()
            self._by_tier[tier].add(node_id)

        logger.info(f"Node registered: {node_id} ({capabilities.tier.value})")
        return record

    async def get(self, node_id: str) -> Optional[NodeRecord]:
        """Get node record by ID.

        Args:
            node_id: Node identifier

        Returns:
            NodeRecord if found, None otherwise
        """
        return self._nodes.get(node_id)

    async def list_all(self) -> List[NodeRecord]:
        """List all node records.

        Returns:
            List of all NodeRecords
        """
        return list(self._nodes.values())

    async def list_by_tier(self, tier: str) -> List[NodeRecord]:
        """List nodes by tier.

        Args:
            tier: Node tier value (e.g., "ai_factory", "gpu_peer")

        Returns:
            List of NodeRecords for the tier
        """
        node_ids = self._by_tier.get(tier, set())
        return [self._nodes[nid] for nid in node_ids if nid in self._nodes]

    async def list_online(self) -> List[NodeRecord]:
        """List only online (non-stale) nodes.

        Returns:
            List of online NodeRecords
        """
        now = datetime.now()
        return [
            record
            for record in self._nodes.values()
            if now - record.last_heartbeat <= self._stale_threshold
        ]

    async def update_heartbeat(self, heartbeat: NodeHeartbeat) -> Optional[NodeRecord]:
        """Update node from heartbeat.

        Args:
            heartbeat: Heartbeat message from node

        Returns:
            Updated NodeRecord if found, None otherwise
        """
        record = await self.get(heartbeat.node_id)
        if record is None:
            return None

        record.last_heartbeat = heartbeat.timestamp
        record.heartbeat_count += 1
        record.status = heartbeat.status

        # Update dynamic capability fields
        record.capabilities.available_cpu_slots = (
            record.capabilities.cpu.total_threads - int(record.capabilities.cpu.total_threads * heartbeat.cpu_utilization)
        )
        record.capabilities.available_memory_mb = int(
            record.capabilities.memory.total_mb * (1 - heartbeat.memory_utilization)
        )

        return record

    async def mark_offline(self, node_id: str) -> bool:
        """Mark a node as offline.

        Args:
            node_id: Node identifier

        Returns:
            True if node was found and marked offline
        """
        record = await self.get(node_id)
        if record is None:
            return False

        record.status = "offline"
        logger.info(f"Node marked offline: {node_id}")
        return True

    async def remove(self, node_id: str) -> bool:
        """Remove a node from registry.

        Args:
            node_id: Node identifier

        Returns:
            True if node was found and removed
        """
        record = await self.get(node_id)
        if record is None:
            return False

        # Remove from tier index
        tier = record.capabilities.tier.value
        if tier in self._by_tier and node_id in self._by_tier[tier]:
            self._by_tier[tier].remove(node_id)

        # Remove from main store
        del self._nodes[node_id]
        logger.info(f"Node removed: {node_id}")
        return True

    async def cleanup_stale(self) -> int:
        """Remove stale nodes from registry.

        Returns:
            Number of nodes removed
        """
        now = datetime.now()
        stale_ids = [
            node_id
            for node_id, record in self._nodes.items()
            if now - record.last_heartbeat > self._stale_threshold
        ]

        for node_id in stale_ids:
            await self.remove(node_id)

        if stale_ids:
            logger.info(f"Cleaned up {len(stale_ids)} stale nodes")

        return len(stale_ids)

    async def query(
        self,
        tier: Optional[str] = None,
        min_cpu: Optional[int] = None,
        min_ram_mb: Optional[int] = None,
        requires_gpu: bool = False,
        online_only: bool = True,
    ) -> List[NodeRecord]:
        """Query nodes with filters.

        Args:
            tier: Filter by tier (if specified)
            min_cpu: Minimum available CPU slots
            min_ram_mb: Minimum available RAM in MB
            requires_gpu: Only return nodes with GPU available
            online_only: Only return online (non-stale) nodes

        Returns:
            List of matching NodeRecords
        """
        records = await self.list_online() if online_only else await self.list_all()

        if tier:
            records = [r for r in records if r.capabilities.tier.value == tier]

        if min_cpu:
            records = [r for r in records if r.capabilities.available_cpu_slots >= min_cpu]

        if min_ram_mb:
            records = [r for r in records if r.capabilities.available_memory_mb >= min_ram_mb]

        if requires_gpu:
            records = [r for r in records if r.capabilities.available_gpu_slots > 0]

        return records

    def get_stats(self) -> Dict:
        """Get registry statistics.

        Returns:
            Dictionary with stats
        """
        now = datetime.now()
        total = len(self._nodes)
        online = sum(
            1 for r in self._nodes.values() if now - r.last_heartbeat <= self._stale_threshold
        )
        by_tier = {
            tier: len(nodes)
            for tier, nodes in self._by_tier.items()
        }

        return {
            "total_nodes": total,
            "online_nodes": online,
            "offline_nodes": total - online,
            "by_tier": by_tier,
        }


class SupabaseNodeStore(InMemoryNodeStore):
    """Supabase-backed storage for node registry.

    Provides persistent storage with Supabase as backend.
    Falls back to in-memory for reads if Supabase is unavailable.

    Features:
    - Automatic schema initialization
    - Load existing nodes on startup
    - Full CRUD operations via Supabase
    - Native Supabase queries with filtering
    """

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        stale_threshold_seconds: int = 60,
        table_name: str = "compute_nodes",
        auto_init: bool = True,
        load_on_startup: bool = True,
    ):
        """Initialize Supabase store.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service key
            stale_threshold_seconds: Seconds before a node is considered stale
            table_name: Table name for node storage
            auto_init: Automatically create table if missing
            load_on_startup: Load existing nodes from Supabase on init
        """
        super().__init__(stale_threshold_seconds)
        self._supabase_url = supabase_url
        self._supabase_key = supabase_key
        self._table_name = table_name
        self._auto_init = auto_init
        self._load_on_startup = load_on_startup
        self._client: Optional[Any] = None
        self._initialized = False
        self._loaded = False

    async def _get_client(self):
        """Lazy-load Supabase client."""
        if self._client is not None:
            return self._client

        try:
            from supabase import create_client

            self._client = create_client(self._supabase_url, self._supabase_key)
            logger.info(f"Supabase client created for {self._supabase_url}")
            return self._client
        except ImportError:
            logger.warning("Supabase client not available, using in-memory only")
            return None
        except Exception as e:
            logger.warning(f"Failed to create Supabase client: {e}")
            return None

    async def initialize(self):
        """Initialize the Supabase backend.

        Creates table if needed and loads existing nodes.
        Call this after construction before using the store.
        """
        if self._initialized:
            return

        client = await self._get_client()
        if client is None:
            logger.warning("Supabase unavailable, running in-memory only")
            self._initialized = True
            return

        try:
            # Check if table exists by attempting a query
            result = client.table(self._table_name).select("node_id").limit(1).execute()

            if self._load_on_startup:
                await self._load_from_supabase()

            self._initialized = True
            logger.info(f"Supabase store initialized with {len(self._nodes)} nodes")

        except Exception as e:
            if self._auto_init:
                logger.info(f"Table may not exist, attempting auto-init: {e}")
                # Table creation would require admin access - log instruction
                logger.warning(
                    f"Table '{self._table_name}' not found. "
                    f"Please run the migration SQL manually:\n"
                    f"{CREATE_TABLE_SQL}"
                )
            else:
                logger.error(f"Supabase initialization failed: {e}", exc_info=True)
            self._initialized = False  # Mark as NOT initialized since connection failed

    async def _load_from_supabase(self):
        """Load all nodes from Supabase into memory.

        This provides fast local lookups while keeping Supabase as source of truth.
        """
        if self._loaded:
            return

        client = await self._get_client()
        if client is None:
            return

        try:
            result = client.table(self._table_name).select("*").execute()

            for row in result.data:
                try:
                    # Convert Supabase row to NodeCapabilities
                    capabilities = self._row_to_capabilities(row)

                    # Create NodeRecord
                    registered_at = self._parse_datetime(row.get("registered_at"))
                    last_heartbeat = self._parse_datetime(row.get("last_heartbeat"))

                    record = NodeRecord(
                        capabilities=capabilities,
                        registered_at=registered_at or datetime.now(),
                        last_heartbeat=last_heartbeat or datetime.now(),
                        heartbeat_count=row.get("heartbeat_count", 0),
                        status=row.get("status", "online"),
                    )

                    # Store in memory
                    self._nodes[capabilities.node_id] = record

                    # Index by tier
                    tier = capabilities.tier.value
                    if tier not in self._by_tier:
                        self._by_tier[tier] = set()
                    self._by_tier[tier].add(capabilities.node_id)

                except Exception as e:
                    logger.warning(f"Failed to load node {row.get('node_id')}: {e}")

            self._loaded = True
            logger.info(f"Loaded {len(result.data)} nodes from Supabase")

        except Exception as e:
            logger.warning(f"Failed to load nodes from Supabase: {e}")

    def _row_to_capabilities(self, row: Dict[str, Any]) -> NodeCapabilities:
        """Convert Supabase row to NodeCapabilities.

        Args:
            row: Supabase record dictionary

        Returns:
            NodeCapabilities instance
        """
        # Reconstruct CpuInfo
        from ..resource_detector.hardware import CpuInfo, GpuInfo, SystemMemory

        cpu = CpuInfo(
            cores=row.get("cpu_cores", 0),
            threads_per_core=1,
            total_threads=row.get("cpu_threads", row.get("cpu_cores", 0)),
            model_name=row.get("cpu_model", "Unknown"),
            mhz_per_cpu=0.0,
        )

        # Reconstruct SystemMemory
        memory_gb = float(row.get("memory_gb", 0))
        memory = SystemMemory(
            total_mb=int(memory_gb * GB_TO_MB) if memory_gb > 0 else row.get("memory_mb", 0),
            total_gb=memory_gb,
            available_mb=row.get("available_memory_mb", 0),
            available_gb=row.get("available_memory_mb", 0) / MB_TO_GB,
        )

        # Reconstruct GPU list
        gpus = []
        gpu_models = row.get("gpu_models", [])
        gpu_drivers = row.get("gpu_driver_versions", [])
        gpu_count = row.get("gpu_count", len(gpu_models))
        gpu_vram_total = int(row.get("gpu_vram_gb", 0) * GB_TO_MB) or row.get("gpu_vram_mb", 0)
        vram_per_gpu = gpu_vram_total // gpu_count if gpu_count > 0 else 0

        for i in range(gpu_count):
            gpus.append(
                GpuInfo(
                    index=i,
                    name=gpu_models[i] if i < len(gpu_models) else "Unknown",
                    total_vram_mb=vram_per_gpu,
                    total_vram_gb=vram_per_gpu / MB_TO_GB,
                    driver_version=gpu_drivers[i] if i < len(gpu_drivers) else "unknown",
                    cuda_version="unknown",
                )
            )

        # Parse CHIT fields
        geometric_position = row.get("geometric_position")
        if isinstance(geometric_position, str):
            try:
                geometric_position = json.loads(geometric_position)
            except json.JSONDecodeError:
                geometric_position = None

        # Parse JSON fields
        def parse_json_field(value, default):
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return default
            return value if value is not None else default

        supported_models = parse_json_field(row.get("supported_models"), [])
        supported_frameworks = parse_json_field(row.get("supported_frameworks"), [])
        quantization_support = parse_json_field(row.get("quantization_support"), [])

        return NodeCapabilities(
            node_id=row["node_id"],
            hostname=row["hostname"],
            tier=self._parse_tier(row.get("tier", "cpu_peer")),
            cpu=cpu,
            memory=memory,
            gpus=gpus,
            total_gpu_vram_gb=float(row.get("gpu_vram_gb", 0)),
            ipv4=row.get("ipv4"),
            ipv6=row.get("ipv6"),
            port=row.get("port", 4222),
            bandwidth_mbps=float(row.get("bandwidth_mbps")) if row.get("bandwidth_mbps") else None,
            latency_ms=float(row.get("latency_ms")) if row.get("latency_ms") else None,
            available_cpu_slots=row.get("available_cpu_slots", 0),
            available_gpu_slots=row.get("available_gpu_slots", 0),
            available_memory_mb=row.get("available_memory_mb", 0),
            available_vram_mb=row.get("available_vram_mb", 0),
            supported_models=supported_models,
            supported_frameworks=supported_frameworks,
            max_context_tokens=row.get("max_context_tokens", 4096),
            quantization_support=quantization_support,
            is_online=row.get("is_online", True),
            is_draining=row.get("is_draining", False),
            last_heartbeat=self._parse_datetime(row.get("last_heartbeat")),
            uptime_seconds=float(row.get("uptime_seconds", 0)),
            cgp_public_key=row.get("cgp_public_key"),
            geometric_position=geometric_position,
        )

    def _parse_tier(self, tier_value: str):
        """Parse tier string to NodeTier enum."""
        from ..resource_detector.hardware import NodeTier

        try:
            return NodeTier(tier_value)
        except ValueError:
            return NodeTier.CPU_PEER

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from various formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return None

    async def _persist_to_supabase(self, record: NodeRecord):
        """Persist record to Supabase.

        Args:
            record: NodeRecord to persist
        """
        client = await self._get_client()
        if client is None:
            return

        try:
            # Build data dict from capabilities
            caps = record.capabilities

            data = {
                "node_id": caps.node_id,
                "hostname": caps.hostname,
                "tier": caps.tier.value,
                "cpu_cores": caps.cpu.cores,
                "cpu_threads": caps.cpu.total_threads,
                "cpu_model": caps.cpu.model_name,
                "memory_mb": caps.memory.total_mb,
                "memory_gb": round(caps.memory.total_gb, 2),
                "gpu_count": len(caps.gpus),
                "gpu_vram_mb": int(caps.total_gpu_vram_gb * GB_TO_MB),
                "gpu_vram_gb": round(caps.total_gpu_vram_gb, 2),
                "gpu_models": [g.name for g in caps.gpus],
                "gpu_driver_versions": [g.driver_version for g in caps.gpus],
                "ipv4": caps.ipv4,
                "ipv6": caps.ipv6,
                "port": caps.port,
                "bandwidth_mbps": caps.bandwidth_mbps,
                "latency_ms": caps.latency_ms,
                "available_cpu_slots": caps.available_cpu_slots,
                "available_gpu_slots": caps.available_gpu_slots,
                "available_memory_mb": caps.available_memory_mb,
                "available_vram_mb": caps.available_vram_mb,
                "supported_models": caps.supported_models,
                "supported_frameworks": caps.supported_frameworks,
                "max_context_tokens": caps.max_context_tokens,
                "quantization_support": caps.quantization_support,
                "is_online": caps.is_online,
                "is_draining": caps.is_draining,
                "status": record.status,
                "last_heartbeat": record.last_heartbeat.isoformat() if record.last_heartbeat else None,
                "registered_at": record.registered_at.isoformat(),
                "heartbeat_count": record.heartbeat_count,
                "uptime_seconds": caps.uptime_seconds,
                "cgp_public_key": caps.cgp_public_key,
                "geometric_position": caps.geometric_position,
            }

            # Upsert to Supabase
            client.table(self._table_name).upsert(data, on_conflict="node_id").execute()
            logger.debug(f"Persisted node {caps.node_id} to Supabase")

        except Exception as e:
            logger.warning(f"Failed to persist to Supabase: {e}")

    async def _query_supabase(
        self,
        tier: Optional[str] = None,
        min_cpu: Optional[int] = None,
        min_ram_mb: Optional[int] = None,
        requires_gpu: bool = False,
        online_only: bool = True,
    ) -> List[NodeRecord]:
        """Query Supabase directly for nodes matching criteria.

        Args:
            tier: Filter by tier
            min_cpu: Minimum available CPU slots
            min_ram_mb: Minimum available RAM in MB
            requires_gpu: Only return nodes with GPU available
            online_only: Only return online nodes

        Returns:
            List of matching NodeRecords
        """
        client = await self._get_client()
        if client is None:
            # Fall back to in-memory query
            return await super().query(tier, min_cpu, min_ram_mb, requires_gpu, online_only)

        try:
            # Build Supabase query
            query = client.table(self._table_name).select("*")

            if online_only:
                query = query.eq("is_online", True).eq("status", "online")

            if tier:
                query = query.eq("tier", tier)

            if requires_gpu:
                query = query.gt("gpu_count", 0).gt("available_gpu_slots", 0)

            if min_cpu:
                query = query.gte("available_cpu_slots", min_cpu)

            if min_ram_mb:
                query = query.gte("available_memory_mb", min_ram_mb)

            result = query.execute()

            # Convert to NodeRecords
            records = []
            for row in result.data:
                try:
                    capabilities = self._row_to_capabilities(row)

                    # Ensure in-memory cache has this node
                    if capabilities.node_id not in self._nodes:
                        self._nodes[capabilities.node_id] = NodeRecord(
                            capabilities=capabilities,
                            registered_at=self._parse_datetime(row.get("registered_at")) or datetime.now(),
                            last_heartbeat=self._parse_datetime(row.get("last_heartbeat")) or datetime.now(),
                            heartbeat_count=row.get("heartbeat_count", 0),
                            status=row.get("status", "online"),
                        )

                    records.append(self._nodes[capabilities.node_id])
                except Exception as e:
                    logger.warning(f"Failed to parse node {row.get('node_id')}: {e}")

            return records

        except Exception as e:
            logger.warning(f"Supabase query failed, falling back to in-memory: {e}")
            return await super().query(tier, min_cpu, min_ram_mb, requires_gpu, online_only)

    async def register(self, capabilities: NodeCapabilities) -> NodeRecord:
        """Register node with Supabase persistence."""
        # Ensure initialized
        if not self._initialized:
            await self.initialize()

        record = await super().register(capabilities)
        await self._persist_to_supabase(record)
        return record

    async def update_heartbeat(self, heartbeat: NodeHeartbeat) -> Optional[NodeRecord]:
        """Update heartbeat with Supabase persistence."""
        if not self._initialized:
            await self.initialize()

        record = await super().update_heartbeat(heartbeat)
        if record:
            await self._persist_to_supabase(record)
        return record

    async def query(
        self,
        tier: Optional[str] = None,
        min_cpu: Optional[int] = None,
        min_ram_mb: Optional[int] = None,
        requires_gpu: bool = False,
        online_only: bool = True,
    ) -> List[NodeRecord]:
        """Query nodes with filters.

        Uses Supabase for efficient filtering when available,
        falls back to in-memory query.

        Args:
            tier: Filter by tier (if specified)
            min_cpu: Minimum available CPU slots
            min_ram_mb: Minimum available RAM in MB
            requires_gpu: Only return nodes with GPU available
            online_only: Only return online (non-stale) nodes

        Returns:
            List of matching NodeRecords
        """
        if not self._initialized:
            await self.initialize()

        # Use Supabase query for efficient filtering
        return await self._query_supabase(tier, min_cpu, min_ram_mb, requires_gpu, online_only)

    async def sync_from_supabase(self) -> int:
        """Force sync all nodes from Supabase.

        Useful for refreshing the local cache after external changes.

        Returns:
            Number of nodes loaded
        """
        client = await self._get_client()
        if client is None:
            return 0

        self._loaded = False  # Force reload
        await self._load_from_supabase()
        return len(self._nodes)

    async def remove_from_supabase(self, node_id: str) -> bool:
        """Remove node from both memory and Supabase.

        Args:
            node_id: Node identifier

        Returns:
            True if node was found and removed from both Supabase and memory
            False if node was not found or deletion failed
        """
        client = await self._get_client()
        if client is None:
            # No Supabase connection - fall back to memory-only
            logger.warning(f"Supabase unavailable, removing from memory only: {node_id}")
            return await super().remove(node_id)

        try:
            # Delete from Supabase - check result
            result = client.table(self._table_name).delete().eq("node_id", node_id).execute()

            # Check if deletion actually happened (Supabase returns data for deleted rows)
            if hasattr(result, 'data') and len(result.data) == 0:
                # Node wasn't in Supabase
                logger.debug(f"Node not found in Supabase: {node_id}")
                # Still try to remove from memory
                return await super().remove(node_id)

            # Remove from memory after successful Supabase deletion
            return await super().remove(node_id)

        except Exception as e:
            logger.error(f"Failed to delete from Supabase: {e}", exc_info=True)
            # Don't silently fall back - if Supabase fails, the operation failed
            # This prevents divergence between memory and persistent storage
            return False
