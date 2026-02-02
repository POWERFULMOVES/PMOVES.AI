"""vLLM Resource Limits Generator.

Generates docker-compose resource limits (CPU, RAM, GPU) for vLLM instances
based on detected hardware and model requirements.

Integrates with resource-detector for hardware-aware allocation.
"""

import dataclasses
import logging
from typing import Dict, List, Optional

from ..resource_detector.hardware import (
    HardwareProfile,
    NodeTier,
    ResourceAllocator,
)

from .config import MODEL_CONFIGS, VLLMConfig, ModelConfig

logger = logging.getLogger(__name__)


# vLLM-specific resource requirements
# These are baseline requirements + model-specific multipliers
VLLM_BASE_REQUIREMENTS = {
    "cpu_cores": 2,  # Minimum for orchestration overhead
    "ram_mb": 4096,  # Base memory for vLLM process
    "shm_size_mb": 16384,  # Shared memory for TP communication
    "overlay_mb": 2048,  # Container overlay filesystem
}


@dataclasses.dataclass
class ResourceLimits:
    """Docker resource limits for a vLLM container."""

    # CPU limits
    cpu_quota: Optional[int] = None  # Microseconds per period (100000 = 1 CPU)
    cpu_period: int = 100000  # Default period (100ms)
    cpu_shares: Optional[int] = None  # Relative weight (1024 = default)
    cpu_count: Optional[float] = None  # Number of CPUs (e.g., 4.5)

    # Memory limits
    memory_mb: Optional[int] = None  # Memory limit (hard)
    memory_reservation_mb: Optional[int] = None  # Soft limit
    memory_swap_mb: Optional[int] = None  # Memory + swap

    # GPU reservations
    gpu_count: int = 1  # Number of GPUs
    gpu_device_ids: Optional[List[str]] = None  # Specific GPU IDs
    vram_per_gpu_mb: Optional[int] = None  # Expected VRAM usage

    # Special resources
    shm_size_mb: int = 16384  # /dev/shm size for TP

    def to_docker_compose(self) -> Dict:
        """Convert to docker-compose resource format."""
        deploy = {"resources": {}}

        # CPU limits
        if self.cpu_count is not None:
            deploy["resources"]["limits"] = deploy["resources"].get("limits", {})
            deploy["resources"]["limits"]["cpus"] = self.cpu_count
        elif self.cpu_quota is not None:
            deploy["resources"]["limits"] = deploy["resources"].get("limits", {})
            deploy["resources"]["limits"]["cpus"] = f"{self.cpu_quota}/{self.cpu_period}"

        if self.cpu_shares is not None:
            deploy["resources"]["reservations"] = deploy["resources"].get("reservations", {})
            deploy["resources"]["reservations"]["cpus"] = f"{self.cpu_shares}/1024"

        # Memory limits
        if self.memory_mb is not None:
            deploy["resources"]["limits"] = deploy["resources"].get("limits", {})
            deploy["resources"]["limits"]["memory"] = f"{self.memory_mb}m"

        if self.memory_reservation_mb is not None:
            deploy["resources"]["reservations"] = deploy["resources"].get("reservations", {})
            deploy["resources"]["reservations"]["memory"] = f"{self.memory_reservation_mb}m"

        if self.memory_swap_mb is not None:
            deploy["resources"]["limits"] = deploy["resources"].get("limits", {})
            deploy["resources"]["limits"]["memory_swap"] = f"{self.memory_swap_mb}m"

        # GPU reservations
        if self.gpu_count > 0:
            device = {
                "driver": "nvidia",
                "count": self.gpu_count,
                "capabilities": ["gpu", "compute", "utility"],
            }
            if self.gpu_device_ids:
                device["device_ids"] = self.gpu_device_ids

            deploy["reservations"] = deploy.get("reservations", {})
            deploy["reservations"]["devices"] = [device]

        # Shared memory
        if self.shm_size_mb > 0:
            deploy["shm_size"] = f"{self.shm_size_mb}m"

        return deploy


@dataclasses.dataclass
class VLLMResourceProfile:
    """Complete resource profile for a vLLM instance."""

    model_name: str
    model_config: ModelConfig
    tensor_parallel_size: int
    pipeline_parallel_size: int

    limits: ResourceLimits
    reservations: ResourceLimits

    # Calculated requirements
    required_vram_mb: int
    required_ram_mb: int
    required_cpu_cores: float

    @property
    def total_gpus(self) -> int:
        """Total GPUs required."""
        return self.tensor_parallel_size * self.pipeline_parallel_size


def calculate_vllm_memory(
    model_config: ModelConfig,
    tensor_parallel_size: int,
    context_length: Optional[int] = None,
    quantization: str = "fp16",
) -> int:
    """Calculate VRAM required for a model.

    Args:
        model_config: Model configuration
        tensor_parallel_size: Number of GPUs for tensor parallelism
        context_length: Context length (uses model default if None)
        quantization: Quantization format

    Returns:
        Required VRAM in MB per GPU
    """
    context = context_length or model_config.context_length

    # Base model weights in bytes (param count * bytes per param)
    bytes_per_param = {"fp16": 2, "int8": 1, "int4": 0.5, "fp32": 4}
    bpw = bytes_per_param.get(quantization, 2)

    model_bytes = model_config.params * bpw
    model_mb = model_bytes / (1024 * 1024)

    # KV cache estimation
    # 2 bytes per token, 32 layers per 1B params (heuristic)
    layers = max(32, model_config.params // 1_000_000_000 * 4)
    kv_cache_bytes = context * layers * 2 * 2
    kv_cache_mb = kv_cache_bytes / (1024 * 1024)

    # Activation memory (rough estimate)
    activation_mb = model_mb * 0.2

    # Total per GPU
    total_mb = (model_mb + kv_cache_mb + activation_mb) / tensor_parallel_size

    # Add overhead (pytorch, cuda, etc.)
    total_mb = total_mb * 1.3

    return int(total_mb)


def calculate_vllm_ram(
    model_config: ModelConfig,
    tensor_parallel_size: int,
    context_length: Optional[int] = None,
) -> int:
    """Calculate system RAM required for a vLLM instance.

    Args:
        model_config: Model configuration
        tensor_parallel_size: Number of GPUs for TP
        context_length: Context length

    Returns:
        Required RAM in MB
    """
    context = context_length or model_config.context_length

    # Base requirements
    base_mb = VLLM_BASE_REQUIREMENTS["ram_mb"]

    # KV cache CPU-side buffer
    kv_cache_mb = context * 100 / (1024 * 1024)  # Rough estimate

    # Model loading overhead (for CPU-side model prep)
    model_overhead_mb = (model_config.params * 2) / (1024 * 1024)

    # TP communication overhead
    tp_overhead_mb = tensor_parallel_size * 256

    # Total
    total_mb = base_mb + kv_cache_mb + model_overhead_mb + tp_overhead_mb

    # Add safety margin
    return int(total_mb * 1.5)


def calculate_vllm_cpu(
    model_config: ModelConfig,
    tensor_parallel_size: int,
    pipeline_parallel_size: int = 1,
) -> float:
    """Calculate CPU cores required for a vLLM instance.

    Args:
        model_config: Model configuration
        tensor_parallel_size: TP size
        pipeline_parallel_size: PP size

    Returns:
        Required CPU cores
    """
    # Base cores for orchestration
    base_cores = VLLM_BASE_REQUIREMENTS["cpu_cores"]

    # Cores for GPU communication
    gpu_cores = tensor_parallel_size * 0.5

    # Cores for request handling (scales with model size)
    request_cores = max(1, model_config.params / 10_000_000_000 * 2)

    # PP communication overhead
    pp_cores = pipeline_parallel_size * 0.5

    total_cores = base_cores + gpu_cores + request_cores + pp_cores

    return round(total_cores, 2)


def generate_resource_limits(
    model_name: str,
    hardware_profile: HardwareProfile,
    tensor_parallel_size: Optional[int] = None,
    pipeline_parallel_size: int = 1,
    context_length: Optional[int] = None,
    quantization: str = "fp16",
    utilization_target: float = 0.9,
) -> VLLMResourceProfile:
    """Generate resource limits for a vLLM instance.

    Args:
        model_name: Name of the model
        hardware_profile: Detected hardware profile
        tensor_parallel_size: TP size (auto-calculated if None)
        pipeline_parallel_size: PP size
        context_length: Target context length
        quantization: Quantization format
        utilization_target: Target resource utilization (0.0-1.0)

    Returns:
        VLLMResourceProfile with calculated limits
    """
    if model_name not in MODEL_CONFIGS:
        raise ValueError(f"Unknown model: {model_name}")

    model_config = MODEL_CONFIGS[model_name]

    # Auto-calculate TP if not specified
    available_gpus = len(hardware_profile.gpus)
    if tensor_parallel_size is None:
        # Calculate optimal TP based on VRAM
        if hardware_profile.gpus:
            vram_per_gpu = hardware_profile.gpus[0].total_vram_mb
            required_vram = calculate_vllm_memory(
                model_config, 1, context_length, quantization
            )
            tp_size = 1
            while tp_size < available_gpus:
                if required_vram / tp_size <= vram_per_gpu * utilization_target:
                    break
                tp_size *= 2
            tensor_parallel_size = min(tp_size, model_config.max_tp_size, available_gpus)
        else:
            tensor_parallel_size = 1

    # Calculate requirements
    required_vram = calculate_vllm_memory(
        model_config, tensor_parallel_size, context_length, quantization
    )
    required_ram = calculate_vllm_ram(model_config, tensor_parallel_size, context_length)
    required_cpu = calculate_vllm_cpu(
        model_config, tensor_parallel_size, pipeline_parallel_size
    )

    # Build limits based on hardware constraints
    limits = ResourceLimits(
        cpu_count=min(required_cpu, hardware_profile.cpu.total_threads * 0.8),
        memory_mb=min(
            required_ram * 1.2,
            hardware_profile.memory.available_mb * utilization_target,
        ),
        gpu_count=tensor_parallel_size * pipeline_parallel_size,
        vram_per_gpu_mb=required_vram,
        shm_size_mb=VLLM_BASE_REQUIREMENTS["shm_size_mb"] * tensor_parallel_size,
    )

    # Build reservations (soft limits)
    reservations = ResourceLimits(
        cpu_count=required_cpu * 0.8,
        memory_reservation_mb=required_ram,
        gpu_count=limits.gpu_count,
    )

    return VLLMResourceProfile(
        model_name=model_name,
        model_config=model_config,
        tensor_parallel_size=tensor_parallel_size,
        pipeline_parallel_size=pipeline_parallel_size,
        limits=limits,
        reservations=reservations,
        required_vram_mb=required_vram,
        required_ram_mb=required_ram,
        required_cpu_cores=required_cpu,
    )


def generate_service_resources(
    profile: HardwareProfile,
    services: Optional[List[str]] = None,
    include_vllm: bool = True,
    vllm_models: Optional[List[str]] = None,
) -> Dict[str, Dict]:
    """Generate docker-compose resources for all services.

    Args:
        profile: Hardware profile
        services: List of services to generate (all if None)
        include_vllm: Include vLLM in resource allocation
        vllm_models: List of vLLM models to reserve for

    Returns:
        Dictionary mapping service names to docker-compose resource dicts
    """
    from ..resource_detector.categories import SERVICE_CATEGORIES

    resources = {}

    # Determine which services to allocate
    if services is None:
        # Use all defined service categories as default
        services = list(SERVICE_CATEGORIES.keys())

    # Calculate total required for vLLM
    vllm_requirements = {}
    if include_vllm and vllm_models:
        for model_name in vllm_models:
            if model_name in MODEL_CONFIGS:
                try:
                    vllm_profile = generate_resource_limits(model_name, profile)
                    vllm_requirements[model_name] = {
                        "gpus": vllm_profile.total_gpus,
                        "ram_mb": vllm_profile.required_ram_mb,
                        "cpu_cores": vllm_profile.required_cpu_cores,
                    }
                except Exception as e:
                    logger.warning(f"Failed to calculate vLLM resources for {model_name}: {e}")

    # Calculate available for other services
    reserved_gpus = sum(r["gpus"] for r in vllm_requirements.values())
    reserved_ram = sum(r["ram_mb"] for r in vllm_requirements.values())
    reserved_cpu = sum(r["cpu_cores"] for r in vllm_requirements.values())

    available_gpus = len(profile.gpus) - reserved_gpus
    available_ram = max(0, profile.memory.available_mb - reserved_ram)
    available_cpu = max(0, profile.cpu.total_threads - reserved_cpu)

    # Allocate resources for each service
    for service_name in services:
        if service_name not in SERVICE_CATEGORIES:
            continue

        req = SERVICE_CATEGORIES[service_name]

        # Check if service can run on available resources
        if req.required_gpu_slots > available_gpus:
            logger.warning(f"Skipping {service_name}: not enough GPU")
            continue

        if req.required_ram_mb > available_ram:
            logger.warning(f"Skipping {service_name}: not enough RAM")
            continue

        # Generate docker-compose resource entry
        service_resources = {
            "deploy": {
                "resources": {
                    "limits": {"cpus": req.required_cpu_slots},
                    "reservations": {"memory": f"{req.required_ram_mb}m"},
                }
            }
        }

        # Add GPU reservation if needed
        if req.required_gpu_slots > 0:
            service_resources["deploy"]["reservations"]["devices"] = [
                {
                    "driver": "nvidia",
                    "count": req.required_gpu_slots,
                    "capabilities": ["gpu"],
                }
            ]

        resources[service_name] = service_resources

        # Deduct from available
        available_gpus -= req.required_gpu_slots
        available_ram -= req.required_ram_mb
        available_cpu -= req.required_cpu_slots

    # Add vLLM resources
    for model_name, req in vllm_requirements.items():
        service_name = f"vllm-{model_name}"

        # Calculate TP size
        vllm_profile = generate_resource_limits(model_name, profile)

        limits = ResourceLimits(
            cpu_count=req["cpu_cores"],
            memory_mb=req["ram_mb"] * 1.2,
            memory_reservation_mb=req["ram_mb"],
            gpu_count=req["gpus"],
            shm_size_mb=VLLM_BASE_REQUIREMENTS["shm_size_mb"] * vllm_profile.tensor_parallel_size,
        )

        resources[service_name] = {"deploy": limits.to_docker_compose()}

    return resources


def generate_compose_with_limits(
    profile: HardwareProfile,
    vllm_models: List[str],
    other_services: Optional[List[str]] = None,
) -> str:
    """Generate complete docker-compose.yml with resource limits.

    Args:
        profile: Hardware profile
        vllm_models: List of vLLM models to include
        other_services: Other services to include (recommended if None)

    Returns:
        YAML content for docker-compose file
    """
    resources = generate_service_resources(
        profile,
        services=other_services,
        include_vllm=True,
        vllm_models=vllm_models,
    )

    # Build YAML
    lines = [
        "# Auto-generated by vllm-orchestrator",
        f"# Hardware: {profile.hostname}",
        f"# CPUs: {profile.cpu.total_threads}, RAM: {profile.memory.total_gb:.1f}GB, GPUs: {len(profile.gpus)}",
        "",
        "version: '3.8'",
        "",
        "services:",
    ]

    for service_name, service_config in resources.items():
        lines.append(f"  {service_name}:")
        lines.extend(_format_dict(service_config, indent=4))

    return "\n".join(lines)


def _format_dict(d: Dict, indent: int = 0) -> List[str]:
    """Format dict as YAML lines."""
    lines = []
    prefix = " " * indent

    for key, value in d.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.extend(_format_dict(value, indent + 2))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  -")
                    for k, v in item.items():
                        lines.append(f"{prefix}    {k}: {v}")
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}{key}: {value}")

    return lines
