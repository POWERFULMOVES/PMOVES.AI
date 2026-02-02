"""Service category definitions with tier constraints.

This module defines which PMOVES.AI services can run on which node tiers,
along with their resource requirements. Used by the work allocator to
match workloads with appropriate nodes.
"""

import dataclasses
from typing import Dict, List, Optional, Set

# Try relative import first (for normal package imports), fallback to direct import
try:
    from .hardware import NodeTier
except ImportError:
    from hardware import NodeTier


@dataclasses.dataclass
class ServiceRequirements:
    """Resource requirements for a service."""

    min_tier: NodeTier
    required_cpu_slots: int
    required_ram_mb: int
    required_gpu_slots: int = 0
    required_vram_mb: int = 0
    max_context_tokens: int = 4096
    supported_models: Optional[List[str]] = None
    quantization_required: bool = False

    @property
    def can_run_on_cpu_only(self) -> bool:
        """Whether this service can run on CPU-only nodes."""
        return self.required_gpu_slots == 0

    def compatible_with(self, tier: NodeTier, has_gpu: bool = False) -> bool:
        """Check if service can run on a given tier."""
        # Tier priority check
        tier_priority = {
            NodeTier.AI_FACTORY: 100,
            NodeTier.WORKER_HUB: 80,
            NodeTier.GPU_PEER: 60,
            NodeTier.CPU_PEER: 40,
            NodeTier.EDGE: 20,
            NodeTier.DISASTER: 10,
        }

        if tier_priority[tier] < tier_priority[self.min_tier]:
            return False

        # GPU requirement check
        if self.required_gpu_slots > 0 and not has_gpu:
            return not tier.can_infer_gpu if tier == NodeTier.CPU_PEER else False

        return True


# Service categories with their tier requirements
SERVICE_CATEGORIES: Dict[str, ServiceRequirements] = {
    # ===== GPU-Heavy Services =====
    "ffmpeg-whisper": ServiceRequirements(
        min_tier=NodeTier.GPU_PEER,
        required_cpu_slots=2,
        required_ram_mb=4096,
        required_gpu_slots=1,
        required_vram_mb=4096,
    ),
    "media-video": ServiceRequirements(
        min_tier=NodeTier.GPU_PEER,
        required_cpu_slots=2,
        required_ram_mb=4096,
        required_gpu_slots=1,
        required_vram_mb=4096,
    ),
    "media-audio": ServiceRequirements(
        min_tier=NodeTier.GPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=2048,
        required_gpu_slots=1,
        required_vram_mb=2048,
    ),
    "hi-rag-gateway-v2-gpu": ServiceRequirements(
        min_tier=NodeTier.GPU_PEER,
        required_cpu_slots=2,
        required_ram_mb=4096,
        required_gpu_slots=1,
        required_vram_mb=4096,
        supported_models=["bge-m3", "nomic-embed-text"],
    ),
    "hi-rag-gateway-gpu": ServiceRequirements(
        min_tier=NodeTier.GPU_PEER,
        required_cpu_slots=2,
        required_ram_mb=4096,
        required_gpu_slots=1,
        required_vram_mb=4096,
    ),
    # ===== vLLM Inference Services =====
    "vllm-8b": ServiceRequirements(
        min_tier=NodeTier.GPU_PEER,
        required_cpu_slots=2,
        required_ram_mb=8192,
        required_gpu_slots=1,
        required_vram_mb=16384,
        max_context_tokens=8192,
        supported_models=["llama-3-8b", "gemma-2-9b"],
    ),
    "vllm-70b": ServiceRequirements(
        min_tier=NodeTier.AI_FACTORY,
        required_cpu_slots=4,
        required_ram_mb=16384,
        required_gpu_slots=4,
        required_vram_mb=40960,
        max_context_tokens=8192,
        supported_models=["llama-3-70b", "mixtral-8x7b", "qwen-2-72b"],
    ),
    "vllm-400b": ServiceRequirements(
        min_tier=NodeTier.AI_FACTORY,
        required_cpu_slots=8,
        required_ram_mb=32768,
        required_gpu_slots=8,
        required_vram_mb=81920,
        max_context_tokens=32768,
        supported_models=["mixtral-8x22b"],
    ),
    # ===== Agent Services =====
    "agent-zero": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=2,
        required_ram_mb=2048,
    ),
    "archon": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=1024,
    ),
    "botz-gateway": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=1024,
    ),
    "gateway-agent": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=1024,
    ),
    # ===== API Services =====
    "hi-rag-gateway-v2": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=1024,
    ),
    "extract-worker": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=2048,
        supported_models=["all-MiniLM-L6-v2"],
    ),
    "langextract": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=512,
    ),
    "presign": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=0.5,
        required_ram_mb=256,
    ),
    "render-webhook": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=0.5,
        required_ram_mb=256,
    ),
    "retrieval-eval": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=1024,
    ),
    # ===== Worker Services =====
    "deepresearch": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=1024,
    ),
    "supaserch": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=1024,
    ),
    "publisher-discord": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=0.5,
        required_ram_mb=256,
    ),
    "mesh-agent": ServiceRequirements(
        min_tier=NodeTier.EDGE,
        required_cpu_slots=0.25,
        required_ram_mb=128,
    ),
    "nats-echo-req": ServiceRequirements(
        min_tier=NodeTier.EDGE,
        required_cpu_slots=0.1,
        required_ram_mb=64,
    ),
    "nats-echo-res": ServiceRequirements(
        min_tier=NodeTier.EDGE,
        required_cpu_slots=0.1,
        required_ram_mb=64,
    ),
    "publisher": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=0.5,
        required_ram_mb=256,
    ),
    "analysis-echo": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=0.5,
        required_ram_mb=256,
    ),
    "graph-linker": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=512,
    ),
    "comfy-watcher": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=0.5,
        required_ram_mb=256,
    ),
    "grayjay-plugin-host": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=512,
    ),
    # ===== Media Ingestion =====
    "pmoves-yt": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=1024,
    ),
    "pdf-ingest": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=1024,
    ),
    "jellyfin-bridge": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=0.5,
        required_ram_mb=256,
    ),
    "invidious-companion-proxy": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=0.5,
        required_ram_mb=256,
    ),
    # ===== Voice Services =====
    "flute-gateway": ServiceRequirements(
        min_tier=NodeTier.GPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=1024,
        required_gpu_slots=1,
        required_vram_mb=2048,
    ),
    # ===== Economy Services =====
    "tokenism-simulator": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=1024,
    ),
    "tokenism-ui": ServiceRequirements(
        min_tier=NodeTier.EDGE,
        required_cpu_slots=0.25,
        required_ram_mb=128,
    ),
    # ===== Monitoring =====
    "channel-monitor": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=0.5,
        required_ram_mb=256,
    ),
    "notebook-sync": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=0.5,
        required_ram_mb=256,
    ),
    # ===== Runner Control =====
    "github-runner-ctl": ServiceRequirements(
        min_tier=NodeTier.CPU_PEER,
        required_cpu_slots=1,
        required_ram_mb=512,
    ),
}


# Tier capabilities matrix
TIER_CAPABILITIES: Dict[NodeTier, Dict[str, any]] = {
    NodeTier.AI_FACTORY: {
        "can_train": True,
        "can_infer_gpu": True,
        "can_embed": True,
        "max_model_params": 70_000_000_000,  # 70B
        "max_batch_size": 32,
        "preferred_services": [
            "ffmpeg-whisper",
            "media-video",
            "hi-rag-gateway-v2-gpu",
            "flute-gateway",
        ],
    },
    NodeTier.WORKER_HUB: {
        "can_train": True,
        "can_infer_gpu": True,
        "can_embed": True,
        "max_model_params": 32_000_000_000,  # 32B
        "max_batch_size": 16,
        "preferred_services": [
            "media-video",
            "hi-rag-gateway-gpu",
            "extract-worker",
        ],
    },
    NodeTier.GPU_PEER: {
        "can_train": False,
        "can_infer_gpu": True,
        "can_embed": True,
        "max_model_params": 8_000_000_000,  # 8B
        "max_batch_size": 8,
        "preferred_services": [
            "media-audio",
            "hi-rag-gateway-v2-gpu",
            "agent-zero",
        ],
    },
    NodeTier.CPU_PEER: {
        "can_train": False,
        "can_infer_gpu": False,
        "can_embed": True,
        "max_model_params": 1_000_000_000,  # 1B (quantized)
        "max_batch_size": 4,
        "preferred_services": [
            "extract-worker",
            "pmoves-yt",
            "agent-zero",
            "archon",
        ],
    },
    NodeTier.EDGE: {
        "can_train": False,
        "can_infer_gpu": False,
        "can_embed": False,
        "max_model_params": 500_000_000,  # 500M (heavily quantized)
        "max_batch_size": 1,
        "preferred_services": [
            "mesh-agent",
            "tokenism-ui",
            "nats-echo-req",
        ],
    },
    NodeTier.DISASTER: {
        "can_train": False,
        "can_infer_gpu": False,
        "can_embed": False,
        "max_model_params": 500_000_000,
        "max_batch_size": 1,
        "preferred_services": [
            "mesh-agent",
            "nats-echo-req",
        ],
    },
}


def get_services_for_tier(tier: NodeTier, has_gpu: bool = False) -> List[str]:
    """Get list of services that can run on a given tier."""
    services = []
    for service_name, requirements in SERVICE_CATEGORIES.items():
        if requirements.compatible_with(tier, has_gpu):
            services.append(service_name)
    return services


def get_preferred_services_for_tier(tier: NodeTier) -> List[str]:
    """Get preferred services for a tier based on capabilities."""
    return TIER_CAPABILITIES.get(tier, {}).get("preferred_services", [])


def can_run_service(service_name: str, tier: NodeTier, has_gpu: bool = False) -> bool:
    """Check if a service can run on a given tier."""
    if service_name not in SERVICE_CATEGORIES:
        return False
    return SERVICE_CATEGORIES[service_name].compatible_with(tier, has_gpu)


def estimate_resource_factor(tier: NodeTier) -> float:
    """Get resource multiplication factor for a tier.

    Higher tiers get more resources per service.
    """
    factors = {
        NodeTier.AI_FACTORY: 1.0,
        NodeTier.WORKER_HUB: 0.8,
        NodeTier.GPU_PEER: 0.6,
        NodeTier.CPU_PEER: 0.4,
        NodeTier.EDGE: 0.2,
        NodeTier.DISASTER: 0.1,
    }
    return factors.get(tier, 0.1)
