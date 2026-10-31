"""Resource Detector Service - Dynamic hardware-based resource allocation.

This service detects system hardware (CPU, RAM, GPU) and generates
appropriate docker-compose resource limits for PMOVES.AI services.

Usage:
    from pmoves.services.resource_detector import get_hardware_profile, generate_resource_limits

    profile = get_hardware_profile()
    print(f"CPU: {profile.cpu.total_threads} threads")
    print(f"RAM: {profile.memory.total_gb:.1f}GB")
    print(f"GPU: {len(profile.gpus)}x {profile.total_gpu_vram_gb:.1f}GB")

    limits = generate_resource_limits()
    print(f"agent-zero limits: {limits['agent-zero']}")

CLI:
    python -m pmoves.services.resource_detector.generate
"""

from .hardware import (
    CpuInfo,
    GpuInfo,
    HardwareDetector,
    HardwareProfile,
    NetworkInterface,
    NetworkInfo,
    NodeTier,
    ResourceAllocator,
    SystemMemory,
    get_hardware_profile,
    generate_resource_limits,
)
from .models import (
    NodeCapabilities,
    WorkRequest,
    WorkAssignment,
    NodeHeartbeat,
)
from .categories import (
    ServiceRequirements,
    SERVICE_CATEGORIES,
    TIER_CAPABILITIES,
    get_services_for_tier,
    get_preferred_services_for_tier,
    can_run_service,
    estimate_resource_factor,
)

__all__ = [
    "CpuInfo",
    "GpuInfo",
    "HardwareDetector",
    "HardwareProfile",
    "NetworkInterface",
    "NetworkInfo",
    "NodeTier",
    "ResourceAllocator",
    "SystemMemory",
    "get_hardware_profile",
    "generate_resource_limits",
    "NodeCapabilities",
    "WorkRequest",
    "WorkAssignment",
    "NodeHeartbeat",
    "ServiceRequirements",
    "SERVICE_CATEGORIES",
    "TIER_CAPABILITIES",
    "get_services_for_tier",
    "get_preferred_services_for_tier",
    "can_run_service",
    "estimate_resource_factor",
]
