"""vLLM TensorZero Integration.

Provides automatic configuration of vLLM instances as TensorZero model providers.
Generates TensorZero gateway configs for dynamic model registration.

Usage:
    from pmoves.services.vllm_orchestrator.tensorzero import (
        generate_tensorzero_config,
        generate_multi_model_config,
        register_model_with_tensorzero,
    )

    # Generate config for a single model
    config = generate_tensorzero_config(
        model_name="llama-3-70b",
        vllm_url="http://localhost:8000",
        tier="ai_factory",
    )

    # Generate config for multiple models
    configs = generate_multi_model_config({
        "llama-3-8b": "http://vllm-8b:8000",
        "llama-3-70b": "http://vllm-70b:8000",
    })

    # Register with running TensorZero gateway
    await register_model_with_tensorzero(
        model_name="llama-3-70b",
        vllm_url="http://vllm-70b:8000",
        tensorzero_url="http://tensorzero:3030",
    )
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# TensorZero gateway configuration structure
TENSORZERO_CONFIG_TEMPLATE = {
    "models": {},
    "functions": {},
    "metrics": {},
    "gateways": {
        "anthropic": {"type": "anthropic", "weight": 1},
        "openai": {"type": "openai", "weight": 1},
    },
}


@dataclass
class TensorZeroModelConfig:
    """Configuration for a vLLM model in TensorZero."""

    model_name: str
    vllm_url: str
    provider_name: str  # Unique provider ID for TensorZero
    tier: str = "gpu_peer"

    # Routing configuration
    weight: float = 1.0  # Load balancing weight
    priority: int = 0  # Higher priority models tried first

    # Model capabilities
    supports_chat: bool = True
    supports_completion: bool = True
    supports_embedding: bool = False

    # Rate limiting
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None

    # Fallback configuration
    fallback_models: List[str] = field(default_factory=list)

    # Cost tracking
    cost_per_input_token: float = 0.0
    cost_per_output_token: float = 0.0


@dataclass
class TensorZeroFunctionConfig:
    """Configuration for a TensorZero function (tool calling, etc.)."""

    function_name: str
    description: str
    models: List[str]  # List of model providers
    default_model: str

    # Tool configuration
    tools: List[Dict[str, Any]] = field(default_factory=list)
    tool_choice: str = "auto"  # auto, required, none

    # JSON mode
    json_mode: bool = False

    # Temperature settings
    temperature: float = 0.7
    max_tokens: int = 4096


def generate_tensorzero_config(
    model_name: str,
    vllm_url: str,
    provider_name: Optional[str] = None,
    tier: str = "gpu_peer",
    weight: float = 1.0,
    supports_embeddings: bool = False,
) -> Dict[str, Any]:
    """Generate TensorZero configuration for a vLLM model.

    Args:
        model_name: Name of the model (e.g., "llama-3-70b")
        vllm_url: URL of the vLLM service
        provider_name: Unique provider name (defaults to vllm-{model_name})
        tier: Node tier for routing
        weight: Load balancing weight
        supports_embeddings: Whether model supports embeddings

    Returns:
        Dictionary suitable for TensorZero config
    """
    if provider_name is None:
        provider_name = f"vllm-{model_name.replace('-', '_')}"

    # Validate URL
    parsed = urlparse(vllm_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid vLLM URL: {vllm_url}")

    config = {
        "models": {
            model_name: [
                {
                    "provider": provider_name,
                    "provider_type": "openai",  # vLLM uses OpenAI-compatible API
                    "base_url": vllm_url,
                    "weight": weight,
                    "tier": tier,
                    "capabilities": {
                        "chat": True,
                        "completion": True,
                        "embedding": supports_embeddings,
                    },
                }
            ]
        },
        "functions": {
            "chat": {
                "models": [model_name],
                "default_model": model_name,
                "tools_enabled": True,
            },
            "completion": {
                "models": [model_name],
                "default_model": model_name,
            },
        },
    }

    if supports_embeddings:
        config["functions"]["embedding"] = {
            "models": [model_name],
            "default_model": model_name,
        }

    return config


def generate_multi_model_config(
    model_urls: Dict[str, str],
    tiers: Optional[Dict[str, str]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Generate TensorZero config for multiple vLLM models.

    Args:
        model_urls: Mapping of model names to vLLM URLs
        tiers: Optional mapping of model names to tiers
        weights: Optional mapping of model names to weights

    Returns:
        Complete TensorZero configuration dictionary
    """
    tiers = tiers or {}
    weights = weights or {}

    merged_config = {"models": {}, "functions": {}}
    all_models = []

    for model_name, vllm_url in model_urls.items():
        config = generate_tensorzero_config(
            model_name=model_name,
            vllm_url=vllm_url,
            tier=tiers.get(model_name, "gpu_peer"),
            weight=weights.get(model_name, 1.0),
        )

        # Merge models
        if "models" in config:
            merged_config["models"].update(config["models"])

        all_models.append(model_name)

    # Add functions that use all available models
    merged_config["functions"] = {
        "chat": {
            "models": all_models,
            "default_model": all_models[0] if all_models else None,
            "tools_enabled": True,
            "routing": [
                {"model": m, "weight": weights.get(m, 1.0)}
                for m in all_models
            ] if len(all_models) > 1 else None,
        },
        "completion": {
            "models": all_models,
            "default_model": all_models[0] if all_models else None,
        },
    }

    return merged_config


def generate_hierarchical_config(
    model_groups: Dict[str, Dict[str, str]],
    default_group: str = "small",
) -> Dict[str, Any]:
    """Generate hierarchical config with model groups by capability.

    Args:
        model_groups: Mapping of group names to {model_name: url} dicts
            E.g., {"small": {"llama-3-8b": "http://..."}, "large": {...}}
        default_group: Default group to use

    Returns:
        TensorZero config with function-based routing
    """
    config = {"models": {}, "functions": {}}
    all_models = []

    # Build model configs
    for group, models in model_groups.items():
        for model_name, vllm_url in models.items():
            provider_name = f"vllm_{group}_{model_name.replace('-', '_')}"
            model_config = generate_tensorzero_config(
                model_name=model_name,
                vllm_url=vllm_url,
                provider_name=provider_name,
                tier=group,
            )

            if "models" in model_config:
                config["models"].update(model_config["models"])
                all_models.append(model_name)

    # Build function routing based on capabilities
    config["functions"] = {
        "chat_simple": {
            "models": [m for models in model_groups.get("small", {}).values() for m in models],
            "default_model": list(model_groups.get("small", {}).keys())[0] if model_groups.get("small") else None,
            "description": "Fast chat for simple queries",
        },
        "chat_complex": {
            "models": all_models,
            "default_model": list(model_groups.get("large", {}).keys())[0] if model_groups.get("large") else None,
            "description": "Complex reasoning with larger models",
        },
        "chat": {
            "models": all_models,
            "default_model": list(model_groups.get(default_group, {}).keys())[0] if model_groups.get(default_group) else None,
            "routing": "hierarchical",
        },
    }

    return config


async def register_model_with_tensorzero(
    model_name: str,
    vllm_url: str,
    tensorzero_url: str = "http://localhost:3030",
    provider_name: Optional[str] = None,
    tier: str = "gpu_peer",
) -> bool:
    """Dynamically register a vLLM model with TensorZero gateway.

    Args:
        model_name: Name of the model
        vllm_url: URL of the vLLM service
        tensorzero_url: URL of TensorZero gateway
        provider_name: Unique provider name
        tier: Node tier for routing

    Returns:
        True if registration succeeded
    """
    import aiohttp

    if provider_name is None:
        provider_name = f"vllm-{model_name.replace('-', '_')}"

    config = {
        "model_name": model_name,
        "provider": provider_name,
        "provider_type": "openai",
        "base_url": vllm_url,
        "tier": tier,
        "capabilities": {
            "chat": True,
            "completion": True,
        },
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{tensorzero_url}/models/register",
                json=config,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status in (200, 201):
                    logger.info(f"Registered {model_name} with TensorZero at {tensorzero_url}")
                    return True
                else:
                    error_text = await resp.text()
                    logger.error(f"Failed to register model: {resp.status} - {error_text}")
                    return False

    except aiohttp.ClientError as e:
        logger.error(f"Failed to connect to TensorZero at {tensorzero_url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error registering model: {e}")
        return False


async def unregister_model_from_tensorzero(
    model_name: str,
    tensorzero_url: str = "http://localhost:3030",
    provider_name: Optional[str] = None,
) -> bool:
    """Unregister a model from TensorZero gateway.

    Args:
        model_name: Name of the model
        tensorzero_url: URL of TensorZero gateway
        provider_name: Provider name (defaults to vllm-{model_name})

    Returns:
        True if unregistration succeeded
    """
    import aiohttp

    if provider_name is None:
        provider_name = f"vllm-{model_name.replace('-', '_')}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{tensorzero_url}/models/{provider_name}",
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status in (200, 204):
                    logger.info(f"Unregistered {model_name} from TensorZero")
                    return True
                else:
                    logger.warning(f"Failed to unregister model: {resp.status}")
                    return False

    except Exception as e:
        logger.error(f"Error unregistering model: {e}")
        return False


async def discover_vllm_models(
    node_registry_url: str = "http://localhost:8082",
    tensorzero_url: str = "http://localhost:3030",
) -> List[str]:
    """Discover vLLM models from node registry and register with TensorZero.

    Args:
        node_registry_url: URL of node registry API
        tensorzero_url: URL of TensorZero gateway

    Returns:
        List of registered model names
    """
    import aiohttp

    registered = []

    try:
        async with aiohttp.ClientSession() as session:
            # Query for GPU nodes with vLLM
            async with session.get(
                f"{node_registry_url}/nodes",
                params={
                    "tier": "gpu_peer",
                    "online_only": "true",
                },
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to query node registry: {resp.status}")
                    return registered

                nodes = await resp.json()
                nodes_data = nodes.get("nodes", [])

                for node in nodes_data:
                    # Check for vLLM capability
                    supported_models = node.get("supported_models", [])

                    # Build vLLM URL for this node
                    ipv4 = node.get("ipv4")
                    if not ipv4:
                        continue

                    for model in supported_models:
                        vllm_url = f"http://{ipv4}:8000/v1"

                        # Try to register if vLLM is healthy
                        try:
                            async with session.get(f"{vllm_url.replace('/v1', '')}/health", timeout=aiohttp.ClientTimeout(total=2)) as health_resp:
                                if health_resp.status == 200:
                                    if await register_model_with_tensorzero(
                                        model_name=model,
                                        vllm_url=vllm_url,
                                        tensorzero_url=tensorzero_url,
                                        tier=node.get("tier", "gpu_peer"),
                                    ):
                                        registered.append(model)
                        except Exception:
                            pass  # vLLM not available on this node

    except Exception as e:
        logger.error(f"Error discovering vLLM models: {e}")

    return registered


async def sync_vllm_to_tensorzero(
    vllm_configs: List[Dict[str, Any]],
    tensorzero_url: str = "http://localhost:3030",
    config_path: str = "/etc/tensorzero/config.json",
) -> bool:
    """Generate and deploy TensorZero config for vLLM models.

    Args:
        vllm_configs: List of vLLM config dicts with model_name, url, tier
        tensorzero_url: URL of TensorZero gateway
        config_path: Path to write config file

    Returns:
        True if sync succeeded
    """
    # Build model URL mapping
    model_urls = {c["model_name"]: c["url"] for c in vllm_configs}
    tiers = {c["model_name"]: c.get("tier", "gpu_peer") for c in vllm_configs}
    weights = {c["model_name"]: c.get("weight", 1.0) for c in vllm_configs}

    # Generate config
    config = generate_multi_model_config(model_urls, tiers, weights)

    # Write config file
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Wrote TensorZero config to {config_path}")
    except Exception as e:
        logger.error(f"Failed to write config: {e}")
        return False

    # Reload TensorZero if it has a reload endpoint
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{tensorzero_url}/admin/reload") as resp:
                if resp.status == 200:
                    logger.info("Triggered TensorZero config reload")
    except Exception as e:
        logger.warning(f"Could not trigger TensorZero reload: {e}")

    return True


def generate_docker_compose_override(
    vllm_models: List[Dict[str, Any]],
    tensorzero_port: int = 3030,
) -> str:
    """Generate docker-compose override file for vLLM + TensorZero.

    Args:
        vllm_models: List of {name, model, url} dicts
        tensorzero_port: TensorZero gateway port

    Returns:
        YAML content for docker-compose.override.yml
    """
    lines = [
        "# Auto-generated by vllm-orchestrator",
        "# TensorZero integration for vLLM models",
        "",
        "version: '3.8'",
        "",
        "services:",
        "  tensorzero-gateway:",
        f"    ports:",
        f'      - "{tensorzero_port}:3030"',
        "    environment:",
        "      - TENSORZERO_MODEL_CONFIG_FILE=/config/tensorzero.json",
        "    volumes:",
        "      - ./tensorzero.json:/config/tensorzero.json:ro",
        "",
    ]

    # Add vLLM services
    for i, model in enumerate(vllm_models):
        name = model.get("name", f"vllm-{i}")
        model_name = model.get("model", "llama-3-8b")
        port = 8000 + i

        lines.extend([
            f"  {name}:",
            "    image: vllm/vllm-openai:latest",
            f"    command: '--model {model_name} --port 8000'",
            f"    ports:",
            f'      - "{port}:8000"',
            "    deploy:",
            "      resources:",
            "        reservations:",
            "          devices:",
            '            - driver: nvidia',
            "              count: all",
            "              capabilities: [gpu]",
            "",
        ])

    return "\n".join(lines)


def export_tensorzero_config(
    model_urls: Dict[str, str],
    output_path: str = "tensorzero.json",
    format: str = "json",
) -> str:
    """Export TensorZero config to file.

    Args:
        model_urls: Mapping of model names to vLLM URLs
        output_path: Path to write config
        format: Output format (json or yaml)

    Returns:
        Path to written file
    """
    config = generate_multi_model_config(model_urls)

    if format == "yaml":
        try:
            import yaml

            with open(output_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
        except ImportError:
            # Fallback to JSON if pyyaml not available
            with open(output_path, "w") as f:
                json.dump(config, f, indent=2)
    else:
        with open(output_path, "w") as f:
            json.dump(config, f, indent=2)

    logger.info(f"Exported TensorZero config to {output_path}")
    return output_path
