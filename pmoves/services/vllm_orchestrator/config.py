"""vLLM Orchestrator Configuration.

Manages vLLM container settings including tensor parallelism (TP),
pipeline parallelism (PP), and resource allocation.

Integrates with Hugging Face Hub for model discovery and metadata.
"""

import dataclasses
import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

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


# Common model configurations (legacy - kept for backward compatibility)
# New code should use HF_MODEL_CATALOG from load_hf_model_catalog()
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


# =============================================================================
# Hugging Face Model Catalog Integration
# =============================================================================

@dataclasses.dataclass
class HFModelConfig:
    """Extended model configuration from Hugging Face catalog."""

    # Basic identity
    pmoves_name: str
    hf_id: str

    # Model specs
    params: int
    context_length: int
    quantization: str

    # Hardware requirements
    tier: str  # small, medium, large, xlarge
    min_vram_mb: int
    recommended_tp_size: int
    max_tp_size: int
    supports_pp: bool

    # Backend support
    backends: List[str]  # ollama, vllm, llama_cpp, transformers

    # Use cases
    uses: List[str]  # orchestrator, coding, utility, vl_sentinel, etc.

    # Ollama specific
    ollama_name: Optional[str] = None
    ollama_variant: Optional[str] = None

    # vLLM specific
    vllm_name: Optional[str] = None

    # Optional embedding dimensions
    dimensions: Optional[int] = None


def _parse_params(params_str: str) -> int:
    """Parse parameter string like '7B' or '3.8B' to integer."""
    params_str = params_str.lower().replace('b', '').strip()
    if '.' in params_str:
        # Handle '3.8B' -> 3800000000
        return int(float(params_str) * 1_000_000_000)
    return int(params_str) * 1_000_000_000


def load_hf_model_catalog() -> Dict[str, HFModelConfig]:
    """Load model catalog from Hugging Face configuration files.

    Searches for models.yaml in the following locations:
    1. /app/config/models.yaml (in container)
    2. ../../config/models.yaml (relative to vllm-orchestrator)
    3. /pmoves/config/models.yaml (absolute path)

    Returns:
        Dictionary mapping pmoves_name to HFModelConfig
    """
    catalog_path = os.environ.get(
        "HF_MODEL_CATALOG",
        "/pmoves/config/models.yaml"
    )

    if not Path(catalog_path).exists():
        # Try relative path
        relative_path = Path(__file__).parent.parent.parent / "config" / "models.yaml"
        if relative_path.exists():
            catalog_path = str(relative_path)
        else:
            # Fall back to built-in models
            return _get_builtin_hf_catalog()

    try:
        with open(catalog_path) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: Failed to load HF catalog from {catalog_path}: {e}")
        return _get_builtin_hf_catalog()

    catalog = {}

    for tier_name, models in data.get("models", {}).items():
        if tier_name == "specialized":
            for model_data in models:
                config = _hf_model_from_dict(model_data, tier_name)
                catalog[config.pmoves_name] = config
        else:
            for model_data in models:
                config = _hf_model_from_dict(model_data, tier_name)
                catalog[config.pmoves_name] = config

    return catalog


def _hf_model_from_dict(data: Dict[str, Any], tier: str) -> HFModelConfig:
    """Create HFModelConfig from dictionary."""
    params = _parse_params(data["params"]) if isinstance(data["params"], str) else data["params"]

    return HFModelConfig(
        pmoves_name=data["name"],
        hf_id=data["hf_id"],
        params=params,
        context_length=data.get("context", 4096),
        quantization=data.get("quantization", "fp16"),
        tier=tier,
        min_vram_mb=data.get("vram_min", 0),
        recommended_tp_size=data.get("tp_size", 1),
        max_tp_size=data.get("max_tp_size", 8),
        supports_pp=data.get("supports_pp", False),
        backends=data.get("backends", ["transformers"]),
        uses=data.get("uses", []),
        ollama_name=data.get("ollama_name"),
        vllm_name=data.get("vllm_name"),
        dimensions=data.get("dimensions"),
    )


def _get_builtin_hf_catalog() -> Dict[str, HFModelConfig]:
    """Built-in HF model catalog as fallback."""
    return {
        "qwen2.5-7b": HFModelConfig(
            pmoves_name="qwen2.5-7b",
            hf_id="Qwen/Qwen2.5-7B-Instruct",
            params=7_000_000_000,
            context_length=32768,
            quantization="fp16",
            tier="medium",
            min_vram_mb=16384,
            recommended_tp_size=1,
            max_tp_size=2,
            supports_pp=False,
            backends=["ollama", "vllm"],
            uses=["orchestrator", "coding", "utility"],
            ollama_name="qwen2.5:7b",
            vllm_name="Qwen/Qwen2.5-7B-Instruct",
        ),
        "qwen2.5-14b": HFModelConfig(
            pmoves_name="qwen2.5-14b",
            hf_id="Qwen/Qwen2.5-14B-Instruct",
            params=14_000_000_000,
            context_length=32768,
            quantization="fp16",
            tier="medium",
            min_vram_mb=24576,
            recommended_tp_size=1,
            max_tp_size=2,
            supports_pp=False,
            backends=["ollama", "vllm"],
            uses=["orchestrator", "coding"],
            ollama_name="qwen2.5:14b",
            vllm_name="Qwen/Qwen2.5-14B-Instruct",
        ),
        "qwen2.5-32b": HFModelConfig(
            pmoves_name="qwen2.5-32b",
            hf_id="Qwen/Qwen2.5-32B-Instruct",
            params=32_000_000_000,
            context_length=32768,
            quantization="fp16",
            tier="large",
            min_vram_mb=49152,
            recommended_tp_size=2,
            max_tp_size=4,
            supports_pp=True,
            backends=["vllm"],
            uses=["orchestrator", "research"],
            vllm_name="Qwen/Qwen2.5-32B-Instruct",
        ),
        "qwen2.5-coder-7b": HFModelConfig(
            pmoves_name="qwen2.5-coder-7b",
            hf_id="Qwen/Qwen2.5-Coder-7B-Instruct",
            params=7_000_000_000,
            context_length=32768,
            quantization="fp16",
            tier="medium",
            min_vram_mb=16384,
            recommended_tp_size=1,
            max_tp_size=2,
            supports_pp=False,
            backends=["ollama", "vllm"],
            uses=["coding"],
            ollama_name="qwen2.5-coder:7b",
            vllm_name="Qwen/Qwen2.5-Coder-7B-Instruct",
        ),
        "llama3.1-8b": HFModelConfig(
            pmoves_name="llama3.1-8b",
            hf_id="meta-llama/Llama-3.1-8B-Instruct",
            params=8_000_000_000,
            context_length=128000,
            quantization="fp16",
            tier="medium",
            min_vram_mb=16384,
            recommended_tp_size=1,
            max_tp_size=4,
            supports_pp=False,
            backends=["ollama", "vllm"],
            uses=["orchestrator", "utility"],
            ollama_name="llama3.1:8b",
            vllm_name="meta-llama/Llama-3.1-8B-Instruct",
        ),
        "qwen3-vl-8b": HFModelConfig(
            pmoves_name="qwen3-vl-8b",
            hf_id="Qwen/Qwen3-VL-8B-Instruct",
            params=8_000_000_000,
            context_length=32768,
            quantization="fp16",
            tier="medium",
            min_vram_mb=16384,
            recommended_tp_size=1,
            max_tp_size=2,
            supports_pp=False,
            backends=["vllm"],
            uses=["vl_sentinel"],
            vllm_name="Qwen/Qwen3-VL-8B-Instruct",
        ),
        "qwen3-embedding-8b": HFModelConfig(
            pmoves_name="qwen3-embedding-8b",
            hf_id="Qwen/Qwen3-Embedding-8B",
            params=8_000_000_000,
            context_length=32768,
            quantization="fp16",
            tier="medium",
            min_vram_mb=16384,
            recommended_tp_size=1,
            max_tp_size=2,
            supports_pp=False,
            backends=["ollama", "vllm"],
            uses=["embeddings", "hirag"],
            ollama_name="qwen3-embedding:8b",
            vllm_name="Qwen/Qwen3-Embedding-8B",
            dimensions=4096,
        ),
    }


def get_hf_model_config(model_name: str) -> Optional[HFModelConfig]:
    """Get HF model config by name.

    Args:
        model_name: PMOVES model name (e.g., 'qwen2.5-7b')

    Returns:
        HFModelConfig or None if not found
    """
    catalog = load_hf_model_catalog()
    return catalog.get(model_name)


def list_models_by_tier(tier: str, use_case: Optional[str] = None) -> List[HFModelConfig]:
    """List models by hardware tier and optional use case.

    Args:
        tier: Hardware tier (small, medium, large, xlarge)
        use_case: Optional filter by use case (coding, orchestrator, etc.)

    Returns:
        List of matching HFModelConfig
    """
    catalog = load_hf_model_catalog()

    results = [
        config for config in catalog.values()
        if config.tier == tier
    ]

    if use_case:
        results = [c for c in results if use_case in c.uses]

    return results


def recommend_models_for_hardware(
    available_gpus: int,
    vram_per_gpu_mb: int,
) -> List[HFModelConfig]:
    """Recommend models based on available hardware.

    Args:
        available_gpus: Number of GPUs available
        vram_per_gpu_mb: VRAM per GPU in MB

    Returns:
        List of recommended HFModelConfig sorted by suitability
    """
    total_vram_mb = available_gpus * vram_per_gpu_mb

    catalog = load_hf_model_catalog()
    recommendations = []

    for config in catalog.values():
        # Check if model fits in VRAM
        if config.min_vram_mb <= total_vram_mb:
            # Check TP requirements
            if config.recommended_tp_size <= available_gpus:
                recommendations.append(config)

    # Sort by parameter count (larger models first)
    recommendations.sort(key=lambda c: c.params, reverse=True)

    return recommendations


def hf_config_to_model_config(hf_config: HFModelConfig) -> ModelConfig:
    """Convert HFModelConfig to legacy ModelConfig.

    Args:
        hf_config: HFModelConfig to convert

    Returns:
        ModelConfig
    """
    return ModelConfig(
        name=hf_config.pmoves_name,
        params=hf_config.params,
        context_length=hf_config.context_length,
        quantization=hf_config.quantization,
        requires_gpu=True,
        min_vram_mb=hf_config.min_vram_mb,
        recommended_tp_size=hf_config.recommended_tp_size,
        max_tp_size=hf_config.max_tp_size,
        supports_pp=hf_config.supports_pp,
    )


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
        return os.environ.get("VLLM_DOCKER_IMAGE", "vllm/vllm-openai:latest")

    @property
    def hf_model_id(self) -> Optional[str]:
        """Get Hugging Face model ID if available."""
        hf_catalog = load_hf_model_catalog()
        hf_config = hf_catalog.get(self.model_name)
        return hf_config.hf_id if hf_config else None

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
                "test": ["CMD", "curl", "http://localhost:8000/health"],
                "interval": "10s",
                "timeout": "5s",
                "retries": 3,
            },
        }

        return {"services": {f"vllm-{self.model_name}": service}}

    def _vllm_command(self) -> str:
        """Generate vLLM server command."""
        # Use HF model ID if available, otherwise use model_name
        model_to_use = self.hf_model_id or self.model_name

        cmd_parts = [
            "--model", model_to_use,
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

        # Add quantization if specified
        if self.quantization and self.quantization != "fp16":
            if self.quantization == "awq":
                cmd_parts.extend(["--quantization", "awq"])
            elif self.quantization == "gptq":
                cmd_parts.extend(["--quantization", "gptq"])
            elif self.quantization == "fp8":
                cmd_parts.extend(["--quantization", "fp8"])

        # Add max model length if context is specified
        if self.model_config.context_length > 4096:
            cmd_parts.extend(["--max-model-len", str(self.model_config.context_length)])

        return " ".join(cmd_parts)

    def _environment(self) -> List[str]:
        """Generate environment variables."""
        return [
            "HF_DATASET_LOADED_LIMIT=500",
            "PYTHONUNBUFFERED=1",
            f"HF_HOME={os.environ.get('HF_HOME', '/models')}",
            f"HF_HUB_CACHE={os.environ.get('HF_HUB_CACHE', '/models/hub')}",
            f"HF_HUB_ENABLE_HF_TRANSFER={os.environ.get('HF_HUB_ENABLE_HF_TRANSFER', '1')}",
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
        model_name: Name of the model (PMOVES name or HF model ID)
        available_gpus: Total GPUs available
        vram_per_gpu_mb: VRAM per GPU in MB
        available_nodes: Number of nodes for PP
        gpus_per_node: GPUs per node for TP
        target_context_length: Target context length

    Returns:
        VLLMConfig with optimal settings
    """
    # Try HF catalog first
    hf_config = get_hf_model_config(model_name)

    if hf_config:
        # Convert HF config to legacy ModelConfig
        model_config = hf_config_to_model_config(hf_config)
        pmoves_name = hf_config.pmoves_name
    elif model_name in MODEL_CONFIGS:
        model_config = MODEL_CONFIGS[model_name]
        pmoves_name = model_name
    else:
        raise ValueError(
            f"Unknown model: {model_name}. "
            f"Available: {list(MODEL_CONFIGS.keys()) + list(load_hf_model_catalog().keys())}"
        )

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
        model_name=pmoves_name,
        model_config=model_config,
        tensor_parallel_size=tp_size,
        pipeline_parallel_size=pp_size,
        strategy=strategy,
        min_tier=min_tier,
        requires_multi_gpu=tp_size > 1,
    )
