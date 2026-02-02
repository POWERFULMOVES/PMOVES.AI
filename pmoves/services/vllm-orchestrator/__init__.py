"""vLLM Orchestrator Service - Dynamic parallelism configuration.

Provides automatic TP/PP sizing for vLLM inference based on available hardware.
Integrates with node registry for resource discovery across the P2P network.

Usage:
    from pmoves.services.vllm_orchestrator import (
        create_vllm_config,
        VLLMOrchestrator,
        run_orchestrator,
        generate_resource_limits,
    )

    # Create configuration for specific hardware
    config = create_vllm_config(
        model_name="llama-3-70b",
        available_gpus=4,
        vram_per_gpu_mb=24576,
    )
    print(f"TP size: {config.tensor_parallel_size}")

    # Generate resource limits for docker-compose
    profile = get_hardware_profile()
    vllm_profile = generate_resource_limits("llama-3-70b", profile)
    print(f"CPU: {vllm_profile.required_cpu_cores}, RAM: {vllm_profile.required_ram_mb}MB")

    # Run as standalone service
    await run_orchestrator(nats_url="nats://localhost:4222")

Supported Models:
    - llama-3-8b, llama-3-70b
    - mixtral-8x7b, mixtral-8x22b
    - gemma-2-27b
    - qwen-2-72b
"""

from .config import (
    VLLMConfig,
    ModelConfig,
    MODEL_CONFIGS,
    ParallelismStrategy,
    create_vllm_config,
    calculate_optimal_tp_size,
    calculate_optimal_pp_size,
)

from .server import VLLMOrchestrator, run_orchestrator

from .resources import (
    ResourceLimits,
    VLLMResourceProfile,
    calculate_vllm_memory,
    calculate_vllm_ram,
    calculate_vllm_cpu,
    generate_resource_limits,
    generate_service_resources,
    generate_compose_with_limits,
)

from .tensorzero import (
    TensorZeroModelConfig,
    TensorZeroFunctionConfig,
    generate_tensorzero_config,
    generate_multi_model_config,
    generate_hierarchical_config,
    register_model_with_tensorzero,
    unregister_model_from_tensorzero,
    discover_vllm_models,
    sync_vllm_to_tensorzero,
    generate_docker_compose_override,
    export_tensorzero_config,
)

__all__ = [
    "VLLMConfig",
    "ModelConfig",
    "MODEL_CONFIGS",
    "ParallelismStrategy",
    "create_vllm_config",
    "calculate_optimal_tp_size",
    "calculate_optimal_pp_size",
    "VLLMOrchestrator",
    "run_orchestrator",
    # Resource limits
    "ResourceLimits",
    "VLLMResourceProfile",
    "calculate_vllm_memory",
    "calculate_vllm_ram",
    "calculate_vllm_cpu",
    "generate_resource_limits",
    "generate_service_resources",
    "generate_compose_with_limits",
    # TensorZero integration
    "TensorZeroModelConfig",
    "TensorZeroFunctionConfig",
    "generate_tensorzero_config",
    "generate_multi_model_config",
    "generate_hierarchical_config",
    "register_model_with_tensorzero",
    "unregister_model_from_tensorzero",
    "discover_vllm_models",
    "sync_vllm_to_tensorzero",
    "generate_docker_compose_override",
    "export_tensorzero_config",
]
