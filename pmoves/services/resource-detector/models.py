"""Data models for PMOVES.AI distributed compute network.

This module defines the core data structures for P2P node coordination,
work marshaling, and capability discovery.
"""

import dataclasses
import datetime
from typing import Dict, List, Optional

# Try relative import first (for normal package imports), fallback to direct import
try:
    from .hardware import CpuInfo, GpuInfo, NodeTier, SystemMemory
except ImportError:
    from hardware import CpuInfo, GpuInfo, NodeTier, SystemMemory


@dataclasses.dataclass
class NodeCapabilities:
    """Complete capability profile for a P2P compute node.

    Sent via NATS during node announcement and used by the work allocator
    to match workloads with appropriate nodes.
    """

    # === Node Identity ===
    node_id: str  # UUID or hostname-based unique identifier
    hostname: str
    tier: NodeTier

    # === Hardware Profile ===
    cpu: CpuInfo
    memory: SystemMemory
    gpus: List[GpuInfo]
    total_gpu_vram_gb: float

    # === Network Info ===
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None
    port: int = 4222  # NATS port
    bandwidth_mbps: Optional[float] = None  # Measured or advertised
    latency_ms: Optional[float] = None  # To coordinator

    # === Availability ===
    available_cpu_slots: int = 0  # Available CPU cores for work
    available_gpu_slots: int = 0  # Available GPUs for work
    available_memory_mb: int = 0  # Available RAM for containers
    available_vram_mb: int = 0  # Available VRAM for models

    # === Service Compatibility ===
    supported_models: List[str] = dataclasses.field(default_factory=list)  # Model families supported
    supported_frameworks: List[str] = dataclasses.field(
        default_factory=lambda: ["pytorch", "vllm", "tensorrt"]
    )
    max_context_tokens: int = 4096  # Max context for LLM inference
    quantization_support: List[str] = dataclasses.field(
        default_factory=lambda: ["fp16", "int8"]
    )

    # === State ===
    is_online: bool = True
    is_draining: bool = False  # True if node is leaving the network
    last_heartbeat: Optional[datetime.datetime] = None
    uptime_seconds: float = 0.0

    # === CHIT Geometry Bus ===
    cgp_public_key: Optional[str] = None  # For geometric swarm coordination
    geometric_position: Optional[Dict[str, float]] = None  # {x, y, z} in hyperbolic space

    def __post_init__(self):
        """Validate node capabilities after initialization."""
        if not self.node_id:
            raise ValueError("node_id cannot be empty")
        if not self.hostname:
            raise ValueError("hostname cannot be empty")
        if self.available_cpu_slots < 0:
            raise ValueError(f"available_cpu_slots must be non-negative, got {self.available_cpu_slots}")
        if self.available_gpu_slots < 0:
            raise ValueError(f"available_gpu_slots must be non-negative, got {self.available_gpu_slots}")
        if self.available_memory_mb < 0:
            raise ValueError(f"available_memory_mb must be non-negative, got {self.available_memory_mb}")
        if self.available_vram_mb < 0:
            raise ValueError(f"available_vram_mb must be non-negative, got {self.available_vram_mb}")
        if self.port < 0 or self.port > 65535:
            raise ValueError(f"port must be in range 0-65535, got {self.port}")
        if self.uptime_seconds < 0:
            raise ValueError(f"uptime_seconds must be non-negative, got {self.uptime_seconds}")
        if self.total_gpu_vram_gb < 0:
            raise ValueError(f"total_gpu_vram_gb must be non-negative, got {self.total_gpu_vram_gb}")

    def to_nats_message(self) -> dict:
        """Convert to NATS message format for node announcement."""
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "tier": self.tier.value,
            "cpu_cores": self.cpu.cores,
            "cpu_threads": self.cpu.total_threads,
            "memory_gb": round(self.memory.total_gb, 1),
            "gpu_count": len(self.gpus),
            "gpu_vram_gb": round(self.total_gpu_vram_gb, 1),
            "gpu_models": [g.name for g in self.gpus],
            "ipv4": self.ipv4,
            "ipv6": self.ipv6,
            "port": self.port,
            "bandwidth_mbps": self.bandwidth_mbps,
            "latency_ms": self.latency_ms,
            "available_cpu_slots": self.available_cpu_slots,
            "available_gpu_slots": self.available_gpu_slots,
            "available_memory_mb": self.available_memory_mb,
            "available_vram_mb": self.available_vram_mb,
            "supported_models": self.supported_models,
            "supported_frameworks": self.supported_frameworks,
            "max_context_tokens": self.max_context_tokens,
            "quantization_support": self.quantization_support,
            "is_online": self.is_online,
            "is_draining": self.is_draining,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "uptime_seconds": self.uptime_seconds,
            "cgp_public_key": self.cgp_public_key,
            "geometric_position": self.geometric_position,
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for storage (e.g., Supabase JSON).

        Similar to to_nats_message but optimized for storage format.
        """
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "tier": self.tier.value,
            "cpu_cores": self.cpu.cores,
            "cpu_threads": self.cpu.total_threads,
            "cpu_model": self.cpu.model_name,
            "cpu_mhz": self.cpu.mhz_per_cpu,
            "memory_mb": self.memory.total_mb,
            "memory_gb": round(self.memory.total_gb, 2),
            "gpu_count": len(self.gpus),
            "gpu_vram_mb": int(self.total_gpu_vram_gb * 1024),
            "gpu_vram_gb": round(self.total_gpu_vram_gb, 2),
            "gpu_models": [g.name for g in self.gpus],
            "gpu_driver_versions": [g.driver_version for g in self.gpus],
            "ipv4": self.ipv4,
            "ipv6": self.ipv6,
            "port": self.port,
            "bandwidth_mbps": self.bandwidth_mbps,
            "latency_ms": self.latency_ms,
            "available_cpu_slots": self.available_cpu_slots,
            "available_gpu_slots": self.available_gpu_slots,
            "available_memory_mb": self.available_memory_mb,
            "available_vram_mb": self.available_vram_mb,
            "supported_models": self.supported_models,
            "supported_frameworks": self.supported_frameworks,
            "max_context_tokens": self.max_context_tokens,
            "quantization_support": self.quantization_support,
            "is_online": self.is_online,
            "is_draining": self.is_draining,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "uptime_seconds": self.uptime_seconds,
            "cgp_public_key": self.cgp_public_key,
            "geometric_position": self.geometric_position,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NodeCapabilities":
        """Create from dictionary format (e.g., Supabase JSON).

        Similar to from_nats_message but handles storage format.
        """
        # Reconstruct CpuInfo
        cpu = CpuInfo(
            cores=data.get("cpu_cores", 0),
            threads_per_core=1,
            total_threads=data.get("cpu_threads", data.get("cpu_cores", 0)),
            model_name=data.get("cpu_model", "Unknown"),
            mhz_per_cpu=data.get("cpu_mhz", 0.0),
        )

        # Reconstruct SystemMemory
        memory_gb = data.get("memory_gb", 0.0)
        if memory_gb == 0.0:
            memory_mb = data.get("memory_mb", 0)
            memory_gb = memory_mb / 1024 if memory_mb > 0 else 0.0

        memory = SystemMemory(
            total_mb=data.get("memory_mb", int(memory_gb * 1024)),
            total_gb=memory_gb,
            available_mb=data.get("available_memory_mb", 0),
            available_gb=data.get("available_memory_mb", 0) / 1024,
        )

        # Reconstruct GPU list
        gpus = []
        gpu_names = data.get("gpu_models", [])
        gpu_drivers = data.get("gpu_driver_versions", [])
        gpu_vram_total = data.get("gpu_vram_mb", 0) or data.get("gpu_vram_gb", 0) * 1024

        gpu_count = data.get("gpu_count", len(gpu_names))
        vram_per_gpu = gpu_vram_total // gpu_count if gpu_count > 0 else 0

        for i in range(gpu_count):
            gpus.append(
                GpuInfo(
                    index=i,
                    name=gpu_names[i] if i < len(gpu_names) else "Unknown",
                    total_vram_mb=vram_per_gpu,
                    total_vram_gb=vram_per_gpu / 1024,
                    driver_version=gpu_drivers[i] if i < len(gpu_drivers) else "unknown",
                    cuda_version="unknown",
                )
            )

        # Handle timestamp parsing
        last_heartbeat = None
        if data.get("last_heartbeat"):
            try:
                last_heartbeat = datetime.datetime.fromisoformat(data["last_heartbeat"])
            except (ValueError, TypeError):
                pass

        return cls(
            node_id=data["node_id"],
            hostname=data["hostname"],
            tier=NodeTier(data["tier"]),
            cpu=cpu,
            memory=memory,
            gpus=gpus,
            total_gpu_vram_gb=data.get("gpu_vram_gb", 0.0),
            ipv4=data.get("ipv4"),
            ipv6=data.get("ipv6"),
            port=data.get("port", 4222),
            bandwidth_mbps=data.get("bandwidth_mbps"),
            latency_ms=data.get("latency_ms"),
            available_cpu_slots=data.get("available_cpu_slots", 0),
            available_gpu_slots=data.get("available_gpu_slots", 0),
            available_memory_mb=data.get("available_memory_mb", 0),
            available_vram_mb=data.get("available_vram_mb", 0),
            supported_models=data.get("supported_models", []),
            supported_frameworks=data.get("supported_frameworks", []),
            max_context_tokens=data.get("max_context_tokens", 4096),
            quantization_support=data.get("quantization_support", []),
            is_online=data.get("is_online", True),
            is_draining=data.get("is_draining", False),
            last_heartbeat=last_heartbeat,
            uptime_seconds=data.get("uptime_seconds", 0.0),
            cgp_public_key=data.get("cgp_public_key"),
            geometric_position=data.get("geometric_position"),
        )

    @classmethod
    def from_nats_message(cls, msg: dict) -> "NodeCapabilities":
        """Create from NATS message format."""
        # Reconstruct CpuInfo and SystemMemory from flat message
        cpu = CpuInfo(
            cores=msg.get("cpu_cores", 0),
            threads_per_core=1,
            total_threads=msg.get("cpu_threads", msg.get("cpu_cores", 0)),
            model_name="Unknown",
            mhz_per_cpu=0.0,
        )
        memory = SystemMemory(
            total_mb=int(msg.get("memory_gb", 0) * 1024),
            total_gb=msg.get("memory_gb", 0.0),
            available_mb=msg.get("available_memory_mb", 0),
            available_gb=msg.get("available_memory_mb", 0) / 1024,
        )

        # Reconstruct GPU list
        gpus = []
        gpu_names = msg.get("gpu_models", [])
        for i, name in enumerate(gpu_names):
            gpus.append(
                GpuInfo(
                    index=i,
                    name=name,
                    total_vram_mb=0,  # Not included in announcement
                    total_vram_gb=0.0,
                    driver_version="unknown",
                    cuda_version="unknown",
                )
            )

        return cls(
            node_id=msg["node_id"],
            hostname=msg["hostname"],
            tier=NodeTier(msg["tier"]),
            cpu=cpu,
            memory=memory,
            gpus=gpus,
            total_gpu_vram_gb=msg.get("gpu_vram_gb", 0.0),
            ipv4=msg.get("ipv4"),
            ipv6=msg.get("ipv6"),
            port=msg.get("port", 4222),
            bandwidth_mbps=msg.get("bandwidth_mbps"),
            latency_ms=msg.get("latency_ms"),
            available_cpu_slots=msg.get("available_cpu_slots", 0),
            available_gpu_slots=msg.get("available_gpu_slots", 0),
            available_memory_mb=msg.get("available_memory_mb", 0),
            available_vram_mb=msg.get("available_vram_mb", 0),
            supported_models=msg.get("supported_models", []),
            supported_frameworks=msg.get("supported_frameworks", []),
            max_context_tokens=msg.get("max_context_tokens", 4096),
            quantization_support=msg.get("quantization_support", []),
            is_online=msg.get("is_online", True),
            is_draining=msg.get("is_draining", False),
            last_heartbeat=datetime.datetime.fromisoformat(msg["last_heartbeat"])
            if msg.get("last_heartbeat")
            else None,
            uptime_seconds=msg.get("uptime_seconds", 0.0),
            cgp_public_key=msg.get("cgp_public_key"),
            geometric_position=msg.get("geometric_position"),
        )

    def can_handle_workload(self, required_cpu: int, required_ram_mb: int, required_gpu: bool = False) -> bool:
        """Check if node can handle a workload."""
        if required_gpu and not self.tier.can_infer_gpu:
            return False
        if self.available_cpu_slots < required_cpu:
            return False
        if self.available_memory_mb < required_ram_mb:
            return False
        return True

    @property
    def utilization_score(self) -> float:
        """Calculate utilization score (0.0-1.0) for load balancing."""
        if not self.is_online or self.is_draining:
            return 1.0  # Full utilization (shouldn't get more work)

        total_capacity = (
            self.cpu.total_threads + self.memory.total_mb / 1024 + len(self.gpus) * 10
        )
        used_capacity = (
            (self.cpu.total_threads - self.available_cpu_slots)
            + (self.memory.total_mb - self.available_memory_mb) / 1024
            + (len(self.gpus) - self.available_gpu_slots) * 10
        )

        return min(1.0, used_capacity / total_capacity if total_capacity > 0 else 1.0)


@dataclasses.dataclass
class WorkRequest:
    """Request for compute resources from the P2P network."""

    request_id: str
    workload_type: str  # "inference", "training", "embedding", "preprocessing"
    model_name: str
    required_cpu_slots: int
    required_ram_mb: int
    required_gpu_slots: int = 0
    required_vram_mb: int = 0
    min_tier: Optional[NodeTier] = None  # Minimum node tier required
    timeout_seconds: int = 300
    metadata: Dict = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        """Validate work request after initialization."""
        if not self.request_id:
            raise ValueError("request_id cannot be empty")
        if not self.workload_type:
            raise ValueError("workload_type cannot be empty")
        if not self.model_name:
            raise ValueError("model_name cannot be empty")
        if self.required_cpu_slots < 0:
            raise ValueError(f"required_cpu_slots must be non-negative, got {self.required_cpu_slots}")
        if self.required_ram_mb <= 0:
            raise ValueError(f"required_ram_mb must be positive, got {self.required_ram_mb}")
        if self.required_gpu_slots < 0:
            raise ValueError(f"required_gpu_slots must be non-negative, got {self.required_gpu_slots}")
        if self.required_vram_mb < 0:
            raise ValueError(f"required_vram_mb must be non-negative, got {self.required_vram_mb}")
        if self.timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {self.timeout_seconds}")

    def to_nats_message(self) -> dict:
        """Convert to NATS message format."""
        return {
            "request_id": self.request_id,
            "workload_type": self.workload_type,
            "model_name": self.model_name,
            "required_cpu_slots": self.required_cpu_slots,
            "required_ram_mb": self.required_ram_mb,
            "required_gpu_slots": self.required_gpu_slots,
            "required_vram_mb": self.required_vram_mb,
            "min_tier": self.min_tier.value if self.min_tier else None,
            "timeout_seconds": self.timeout_seconds,
            "metadata": self.metadata,
        }

    @classmethod
    def from_nats_message(cls, msg: dict) -> "WorkRequest":
        """Create from NATS message format."""
        min_tier = NodeTier(msg["min_tier"]) if msg.get("min_tier") else None
        return cls(
            request_id=msg["request_id"],
            workload_type=msg["workload_type"],
            model_name=msg["model_name"],
            required_cpu_slots=msg["required_cpu_slots"],
            required_ram_mb=msg["required_ram_mb"],
            required_gpu_slots=msg.get("required_gpu_slots", 0),
            required_vram_mb=msg.get("required_vram_mb", 0),
            min_tier=min_tier,
            timeout_seconds=msg.get("timeout_seconds", 300),
            metadata=msg.get("metadata", {}),
        )


@dataclasses.dataclass
class WorkAssignment:
    """Assignment of work to a specific node."""

    request_id: str
    node_id: str
    assigned_at: datetime.datetime
    expires_at: datetime.datetime
    connection_info: Dict[str, str]  # {host, port, api_endpoint}
    estimated_completion_seconds: Optional[float] = None


@dataclasses.dataclass
class NodeHeartbeat:
    """Heartbeat message from a node to show liveness."""

    node_id: str
    timestamp: datetime.datetime
    cpu_utilization: float  # 0.0-1.0
    memory_utilization: float  # 0.0-1.0
    gpu_utilization: List[float]  # Per-GPU 0.0-1.0
    active_jobs: int
    status: str = "online"  # online, busy, draining, offline
