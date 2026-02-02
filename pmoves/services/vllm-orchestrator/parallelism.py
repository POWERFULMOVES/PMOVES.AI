"""Automatic TP/PP size calculation for vLLM.

Calculates optimal tensor parallelism and pipeline parallelism
configuration based on available GPUs, model size, and VRAM.
"""

import dataclasses
import logging
from typing import Dict, List, Optional, Tuple

from ..resource_detector.hardware import GpuInfo, NodeTier

logger = logging.getLogger(__name__)

# Memory estimation constants
ACTIVATION_MEMORY_RATIO = 0.25  # Activation memory is ~25% of weights


@dataclasses.dataclass
class ParallelismConfig:
    """Calculated parallelism configuration."""

    tensor_parallel_size: int  # GPUs per node for TP
    pipeline_parallel_size: int  # Nodes for PP
    total_gpus: int  # Total GPUs required
    strategy: str  # "tp", "pp", or "hybrid"

    # Memory estimates
    estimated_vram_per_gpu_mb: int
    estimated_system_ram_mb: int

    # Constraints
    max_context_length: int
    fits_in_vram: bool
    fits_in_ram: bool

    # Performance expectations
    estimated_tokens_per_second: Optional[float] = None
    interconnect_bandwidth_gbps: Optional[float] = None


class ParallelismCalculator:
    """Calculate optimal TP/PP configuration for given hardware and model.

    Uses model size, available VRAM, and GPU topology to determine
    the best parallelism strategy.
    """

    # NVLink bandwidth by version (GB/s per link)
    NVLINK_BANDWIDTH = {
        "1.0": 20.0,  # P100
        "2.0": 25.0,  # V100
        "3.0": 50.0,  # A100
        "4.0": 70.0,  # H100
    }

    # Approximate parameters per layer for common model architectures
    PARAMS_PER_LAYER = {
        "llama": 8_000_000_000 / 32,  # 8B / 32 layers
        "mixtral": 47_000_000_000 / 32,  # 47B / 32 layers
        "gemma": 27_000_000_000 / 28,  # 27B / 28 layers
        "qwen": 72_000_000_000 / 80,  # 72B / 80 layers
    }

    def __init__(self):
        """Initialize parallelism calculator."""
        self._layer_cache: Dict[str, float] = {}

    def calculate(
        self,
        model_params: int,
        available_gpus: List[GpuInfo],
        vram_per_gpu_mb: int,
        system_ram_mb: int,
        context_length: int = 4096,
        quantization_bits: int = 16,
        model_architecture: str = "llama",
    ) -> ParallelismConfig:
        """Calculate optimal TP/PP configuration.

        Args:
            model_params: Total model parameters
            available_gpus: List of GPU info
            vram_per_gpu_mb: VRAM per GPU in MB
            system_ram_mb: Total system RAM in MB
            context_length: Target context length
            quantization_bits: Bits per parameter (4, 8, 16)
            model_architecture: Model architecture name

        Returns:
            ParallelismConfig with optimal settings
        """
        gpu_count = len(available_gpus)

        # Check for NVLink topology
        has_nvlink = any(gpu.nvlink_enabled for gpu in available_gpus)
        nvlink_version = self._get_nvlink_version(available_gpus)
        interconnect_bw = self.NVLINK_BANDWIDTH.get(nvlink_version, 0.0)

        # Calculate layer count
        layers = self._estimate_layer_count(model_params, model_architecture)

        # Estimate memory requirements
        vram_required, ram_required = self._estimate_memory(
            model_params, layers, context_length, quantization_bits
        )

        # Determine strategy
        if gpu_count == 1:
            # Single GPU - no parallelism
            return ParallelismConfig(
                tensor_parallel_size=1,
                pipeline_parallel_size=1,
                total_gpus=1,
                strategy="none",
                estimated_vram_per_gpu_mb=vram_required,
                estimated_system_ram_mb=ram_required,
                max_context_length=context_length,
                fits_in_vram=vram_required <= vram_per_gpu_mb,
                fits_in_ram=ram_required <= system_ram_mb,
                interconnect_bandwidth_gbps=0.0,
            )

        # Calculate TP size based on VRAM
        tp_size = self._calculate_tp_size(
            vram_required, vram_per_gpu_mb, gpu_count
        )

        # Check if we need PP
        needs_pp = (
            tp_size < gpu_count and  # Have GPUs left over after TP
            model_params > 30_000_000_000  # Large models benefit from PP
        )

        pp_size = 1
        if needs_pp:
            pp_size = gpu_count // tp_size

        strategy = "hybrid" if pp_size > 1 else "tp"

        return ParallelismConfig(
            tensor_parallel_size=tp_size,
            pipeline_parallel_size=pp_size,
            total_gpus=tp_size * pp_size,
            strategy=strategy,
            estimated_vram_per_gpu_mb=vram_required // tp_size,
            estimated_system_ram_mb=ram_required,
            max_context_length=context_length,
            fits_in_vram=vram_required // tp_size <= vram_per_gpu_mb,
            fits_in_ram=ram_required <= system_ram_mb,
            interconnect_bandwidth_gbps=interconnect_bw * tp_size if has_nvlink else None,
        )

    def _estimate_layer_count(self, model_params: int, architecture: str) -> int:
        """Estimate number of layers in model.

        Args:
            model_params: Total parameters
            architecture: Model architecture name

        Returns:
            Estimated layer count
        """
        if architecture in self.PARAMS_PER_LAYER:
            params_per_layer = self.PARAMS_PER_LAYER[architecture]
            return max(32, int(model_params / params_per_layer))

        # Generic estimate (assume 7B = 32 layers)
        return max(32, int(model_params * 32 / 7_000_000_000))

    def _estimate_memory(
        self,
        model_params: int,
        layers: int,
        context_length: int,
        quantization_bits: int,
    ) -> Tuple[int, int]:
        """Estimate VRAM and RAM requirements.

        Args:
            model_params: Model parameters
            layers: Number of layers
            context_length: Context length
            quantization_bits: Bits per parameter

        Returns:
            Tuple of (vram_mb, ram_mb)
        """
        # Model weights in bytes (quantized)
        weights_bytes = (model_params * quantization_bits) // 8
        weights_mb = weights_bytes // (1024 * 1024)

        # KV cache (2 bytes per token per layer for activation, 2 for key+value)
        # This is simplified - actual KV cache depends on hidden dim, heads, etc.
        kv_cache_bytes = context_length * layers * 2 * quantization_bits // 8
        kv_cache_mb = kv_cache_bytes // (1024 * 1024)

        # Activation memory (rough estimate: 25% of weights for inference)
        activation_mb = int(weights_mb * ACTIVATION_MEMORY_RATIO)

        # Overhead (CUDA, fragmentation, etc.)
        overhead_mb = 512  # 512MB overhead

        # VRAM needed (weights + KV cache + activations + overhead)
        vram_mb = weights_mb + kv_cache_mb + activation_mb + overhead_mb

        # System RAM needed (for model loading, CPU offload if needed)
        # Typically 1.5x model size for safe loading
        ram_mb = int(weights_mb * 1.5) + overhead_mb

        return vram_mb, ram_mb

    def _calculate_tp_size(
        self,
        vram_required: int,
        vram_per_gpu_mb: int,
        max_gpus: int,
    ) -> int:
        """Calculate tensor parallelism size.

        Args:
            vram_required: Total VRAM required
            vram_per_gpu_mb: VRAM available per GPU
            max_gpus: Maximum GPUs available

        Returns:
            Optimal TP size (power of 2)
        """
        # Minimum TP size to fit in VRAM
        min_tp = 1
        while vram_required / min_tp > vram_per_gpu_mb * 0.9 and min_tp < max_gpus:
            min_tp *= 2

        # Prefer power of 2 TP sizes
        tp_size = min_tp

        # Cap at available GPUs
        tp_size = min(tp_size, max_gpus)

        # Also cap at 8 (common max for TP)
        tp_size = min(tp_size, 8)

        return tp_size

    def _get_nvlink_version(self, gpus: List[GpuInfo]) -> Optional[str]:
        """Get NVLink version from GPU list.

        Args:
            gpus: List of GPU info

        Returns:
            NVLink version if NVLink present, None otherwise
        """
        for gpu in gpus:
            if gpu.nvlink_version:
                return gpu.nvlink_version
        return None

    def estimate_throughput(
        self,
        config: ParallelismConfig,
        model_params: int,
        gpu_name: str = "A100-80GB",
    ) -> float:
        """Estimate tokens per second throughput.

        Args:
            config: Parallelism configuration
            model_params: Model parameter count
            gpu_name: GPU model name

        Returns:
            Estimated tokens/second
        """
        # Baseline throughput (approximate for A100-80GB)
        # 7B model @ FP16: ~5000 tokens/sec
        baseline_params = 7_000_000_000
        baseline_tps = 5000.0

        # Scale by model size (larger models are slower)
        model_factor = baseline_params / model_params

        # Scale by parallelism (diminishing returns)
        # TP has good scaling, PP has latency overhead
        if config.strategy == "tp":
            parallelism_factor = config.tensor_parallel_size * 0.85
        elif config.strategy == "pp":
            parallelism_factor = config.pipeline_parallel_size * 0.65
        else:  # hybrid
            parallelism_factor = (
                config.tensor_parallel_size * 0.85 +
                (config.pipeline_parallel_size - 1) * 0.5
            )

        # GPU-specific factor
        gpu_factors = {
            "H100": 1.3,
            "A100": 1.0,
            "A40": 0.7,
            "V100": 0.5,
            "RTX 4090": 0.8,
            "RTX 5090": 0.95,
            "RTX 3090": 0.6,
        }

        gpu_factor = 1.0
        for name, factor in gpu_factors.items():
            if name in gpu_name:
                gpu_factor = factor
                break

        estimated_tps = baseline_tps * model_factor * parallelism_factor * gpu_factor

        return max(1.0, estimated_tps)


def calculate_parallelism(
    model_name: str,
    model_params: int,
    gpu_count: int,
    vram_per_gpu_mb: int,
    system_ram_mb: int,
    context_length: int = 4096,
    quantization: str = "fp16",
) -> Dict:
    """Convenience function to calculate parallelism configuration.

    Args:
        model_name: Name of the model
        model_params: Parameter count
        gpu_count: Number of GPUs available
        vram_per_gpu_mb: VRAM per GPU in MB
        system_ram_mb: System RAM in MB
        context_length: Target context length
        quantization: Quantization (fp16, int8, int4)

    Returns:
        Dict with parallelism configuration
    """
    calc = ParallelismCalculator()

    # Create dummy GPU info list
    from ..resource_detector.hardware import GpuInfo

    gpus = [
        GpuInfo(
            index=i,
            name="GPU",
            total_vram_mb=vram_per_gpu_mb,
            total_vram_gb=vram_per_gpu_mb / 1024,
            driver_version="unknown",
            cuda_version="unknown",
        )
        for i in range(gpu_count)
    ]

    # Map quantization string to bits
    quant_bits = {"int4": 4, "int8": 8, "fp16": 16}.get(quantization, 16)

    # Detect architecture from model name
    architecture = "llama"
    for arch in ["llama", "mixtral", "gemma", "qwen"]:
        if arch in model_name.lower():
            architecture = arch
            break

    config = calc.calculate(
        model_params=model_params,
        available_gpus=gpus,
        vram_per_gpu_mb=vram_per_gpu_mb,
        system_ram_mb=system_ram_mb,
        context_length=context_length,
        quantization_bits=quant_bits,
        model_architecture=architecture,
    )

    return {
        "model_name": model_name,
        "tensor_parallel_size": config.tensor_parallel_size,
        "pipeline_parallel_size": config.pipeline_parallel_size,
        "total_gpus": config.total_gpus,
        "strategy": config.strategy,
        "estimated_vram_per_gpu_mb": config.estimated_vram_per_gpu_mb,
        "max_context_length": config.max_context_length,
        "fits_in_vram": config.fits_in_vram,
        "fits_in_ram": config.fits_in_ram,
    }
