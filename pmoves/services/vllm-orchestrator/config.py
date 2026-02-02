"""vLLM Orchestrator Configuration.

Manages vLLM container settings including tensor parallelism (TP),
pipeline parallelism (PP), and resource allocation.
"""

import dataclasses
from enum import Enum
from typing import Dict, List, Optional

from ..resource_detector.hardware import NodeTier


class ParallelismStrategy(Enum):
    """Parallelism strategy for distributed inference."""

    TENSOR_PARALLEL = "tp"  # Split model across GPUs on same node
    PIPELINE_PARALLEL = "pp"  # Split layers across nodes
    HYBRID = "hybrid"  # Combine TP and PP


@dataclasses.dataclass
class ModelConfig:
    """Configuration for a specific model."""

    name: str
    params: int  # Parameter count (e.g., 7_000_000_000 for 7B)
    context_length: int = 4096
    quantization: str = "fp16"  # fp16, int8, int4
    requires_gpu: bool = True
    min_vram_mb: int = 0
    recommended_tp_size: int = 1
    max_tp_size: int = 8
    supports_pp: bool = False


# Common model configurations
MODEL_CONFIGS: Dict[str, ModelConfig] = {
    "llama-3-8b": ModelConfig(
        name="llama-3-8b",
        params=8_000_000_000,
        context_length=8192,
        quantization="fp16",
        requires_gpu=True,
        min_vram_mb=16_384,
        recommended_tp_size=1,
        max_tp_size=4,
        supports_pp=False,
    ),
    "llama-3-70b": ModelConfig(
        name="llama-3-70b",
        params=70_000_000_000,
        context_length=8192,
        quantization="fp16",
        requires_gpu=True,
        min_vram_mb=40_960,
        recommended_tp_size=4,
        max_tp_size=8,
        supports_pp=True,
    ),
    "mixtral-8x7b": ModelConfig(
        name="mixtral-8x7b",
        params=47_000_000_000,
        context_length=32768,
        quantization="fp16",
        requires_gpu=True,
        min_vram_mb=32_768,
        recommended_tp_size=2,
        max_tp_size=8,
        supports_pp=True,
    ),
    "mixtral-8x22b": ModelConfig(
        name="mixtral-8x22b",
        params=141_000_000_000,
        context_length=65536,
        quantization="fp16",
        requires_gpu=True,
        min_vram_mb=81920,
        recommended_tp_size=4,
        max_tp_size=8,
        supports_pp=True,
    ),
    "gemma-2-27b": ModelConfig(
        name="gemma-2-27b",
        params=27_000_000_000,
        context_length=8192,
        quantization="fp16",
        requires_gpu=True,
        min_vram_mb=24576,
        recommended_tp_size=2,
        max_tp_size=4,
        supports_pp=False,
    ),
    "qwen-2-72b": ModelConfig(
        name="qwen-2-72b",
        params=72_000_000_000,
        context_length=128000,
        quantization="fp16",
        requires_gpu=True,
        min_vram_mb=40960,
        recommended_tp_size=4,
        max_tp_size=8,
        supports_pp=True,
    ),
}


@dataclasses.dataclass
class VLLMConfig:
    """Complete vLLM service configuration."""

    model_name: str
    model_config: ModelConfig

    # Parallelism settings
    tensor_parallel_size: int = 1
    pipeline_parallel_size: int = 1
    strategy: ParallelismStrategy = ParallelismStrategy.TENSOR_PARALLEL

    # Resource allocation
    gpu_memory_utilization: float = 0.9
    max_num_seqs: int = 256
    max_num_batched_tokens: int = 4096

    # vLLM engine settings
    trust_remote_code: bool = True
    dtype: str = "auto"
    enable_chunked_prefill: bool = True
    enable_prefix_caching: bool = True

    # Service endpoints
    host: str = "0.0.0.0"
    port: int = 8000
    metrics_port: int = 8001

    # Node constraints
    min_tier: NodeTier = NodeTier.GPU_PEER
    requires_multi_gpu: bool = False

    @property
    def total_parallel_size(self) -> int:
        """Total number of GPUs required."""
        return self.tensor_parallel_size * self.pipeline_parallel_size

    @property
    def docker_image(self) -> str:
        """Docker image for vLLM service."""
        return "vllm/vllm-openai:latest"

    def to_docker_compose(self) -> Dict:
        """Generate docker-compose service configuration.

        Returns:
            Dictionary suitable for docker-compose YAML
        """
        service = {
            "image": self.docker_image,
            "command": self._vllm_command(),
            "environment": self._environment(),
            "ports": [
                f"{self.port}:8000",
                f"{self.metrics_port}:8001",
            ],
            "deploy": {
                "resources": {
                    "reservations": {
                        "devices": [
                            {
                                "driver": "nvidia",
                                "count": self.total_parallel_size,
                                "capabilities": ["gpu"],
                            }
                        ]
                    }
                }
            },
            "shm_size": "16g",  # Required for tensor parallelism
            "volumes": [
                "${MODEL_PATH:-/models}:/root/.cache/huggingface",
            ],
            "healthcheck": {
                "test": ["CMD", "curl", f"http://localhost:8000/health"],
                "interval": "10s",
                "timeout": "5s",
                "retries": 3,
            },
        }

        return {"services": {f"vllm-{self.model_name}": service}}

    def _vllm_command(self) -> str:
        """Generate vLLM server command."""
        cmd_parts = [
            "--model", self.model_name,
            "--tensor-parallel-size", str(self.tensor_parallel_size),
            "--gpu-memory-utilization", str(self.gpu_memory_utilization),
            "--max-num-seqs", str(self.max_num_seqs),
            "--max-num-batched-tokens", str(self.max_num_batched_tokens),
            "--host", self.host,
            "--port", "8000",
            "--metrics-port", str(self.metrics_port),
        ]

        if self.enable_chunked_prefill:
            cmd_parts.extend(["--enable-chunked-prefill"])

        if self.enable_prefix_caching:
            cmd_parts.extend(["--enable-prefix-caching"])

        return " ".join(cmd_parts)

    def _environment(self) -> List[str]:
        """Generate environment variables."""
        return [
            f"HF_DATASET_LOADED_LIMIT=500",
            f"PYTHONUNBUFFERED=1",
        ]


def calculate_optimal_tp_size(
    model_config: ModelConfig,
    available_gpus: int,
    vram_per_gpu_mb: int,
    target_context_length: Optional[int] = None,
) -> int:
    """Calculate optimal tensor parallelism size.

    Args:
        model_config: Model configuration
        available_gpus: Number of GPUs available
        vram_per_gpu_mb: VRAM per GPU in MB
        target_context_length: Target context length (uses model default if None)

    Returns:
        Optimal TP size (1 to available_gpus)
    """
    target_context = target_context_length or model_config.context_length

    # Estimate memory requirement
    # Model weights (bytes) + KV cache for context
    weights_bytes = model_config.params * (2 if model_config.quantization == "fp16" else 1)

    # KV cache estimation (2 bytes per token per layer, assuming 32 layers for 7B model)
    layers = max(32, model_config.params // 1_000_000_000 * 4)
    kv_cache_bytes = target_context * layers * 2 * 2  # 2 tokens, 2 bytes

    # Total memory needed with overhead
    total_bytes = weights_bytes + kv_cache_bytes
    total_mb = total_bytes / (1024 * 1024)

    # Calculate minimum TP size to fit in VRAM
    tp_size = 1
    while tp_size < available_gpus:
        if total_mb / tp_size <= vram_per_gpu_mb * 0.9:  # 90% max utilization
            break
        tp_size *= 2

    # Respect model's max TP size
    tp_size = min(tp_size, model_config.max_tp_size, available_gpus)

    return max(1, tp_size)


def calculate_optimal_pp_size(
    model_config: ModelConfig,
    available_nodes: int,
    gpus_per_node: int,
) -> int:
    """Calculate optimal pipeline parallelism size.

    Args:
        model_config: Model configuration
        available_nodes: Number of nodes available
        gpus_per_node: GPUs per node

    Returns:
        Optimal PP size (1 if model doesn't support PP)
    """
    if not model_config.supports_pp:
        return 1

    # For PP, we want to distribute across nodes
    # Use as many stages as we have nodes, capped at reasonable limit
    pp_size = min(available_nodes, 8)

    # Ensure we have enough GPUs for TP * PP
    total_gpus_needed = model_config.recommended_tp_size * pp_size
    available_total_gpus = available_nodes * gpus_per_node

    if total_gpus_needed > available_total_gpus:
        # Reduce PP size if we don't have enough GPUs
        pp_size = available_total_gpus // model_config.recommended_tp_size

    return max(1, pp_size)


def create_vllm_config(
    model_name: str,
    available_gpus: int = 1,
    vram_per_gpu_mb: int = 24576,
    available_nodes: int = 1,
    gpus_per_node: int = 1,
    target_context_length: Optional[int] = None,
) -> VLLMConfig:
    """Create optimal vLLM configuration for given hardware.

    Args:
        model_name: Name of the model
        available_gpus: Total GPUs available
        vram_per_gpu_mb: VRAM per GPU in MB
        available_nodes: Number of nodes for PP
        gpus_per_node: GPUs per node for TP
        target_context_length: Target context length

    Returns:
        VLLMConfig with optimal settings
    """
    if model_name not in MODEL_CONFIGS:
        raise ValueError(f"Unknown model: {model_name}. Available: {list(MODEL_CONFIGS.keys())}")

    model_config = MODEL_CONFIGS[model_name]

    # Calculate TP size
    tp_size = calculate_optimal_tp_size(
        model_config, available_gpus, vram_per_gpu_mb, target_context_length
    )

    # Calculate PP size if we have multiple nodes
    pp_size = 1
    if available_nodes > 1:
        pp_size = calculate_optimal_pp_size(
            model_config, available_nodes, gpus_per_node
        )

    # Determine strategy
    if pp_size > 1:
        strategy = ParallelismStrategy.HYBRID
    else:
        strategy = ParallelismStrategy.TENSOR_PARALLEL

    # Determine minimum tier based on requirements
    if model_config.params >= 30_000_000_000:  # 30B+
        min_tier = NodeTier.AI_FACTORY
    elif model_config.params >= 8_000_000_000:  # 8B+
        min_tier = NodeTier.GPU_PEER
    else:
        min_tier = NodeTier.CPU_PEER

    return VLLMConfig(
        model_name=model_name,
        model_config=model_config,
        tensor_parallel_size=tp_size,
        pipeline_parallel_size=pp_size,
        strategy=strategy,
        min_tier=min_tier,
        requires_multi_gpu=tp_size > 1,
    )
