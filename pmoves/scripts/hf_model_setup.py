#!/usr/bin/env python3
"""
Interactive Hugging Face model setup for PMOVES.AI.

Guides users through:
1. Hardware detection (GPU count, VRAM)
2. Model recommendation based on hardware
3. Model download and caching
4. TensorZero configuration generation
5. Service startup
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# Hardware Detection
# =============================================================================

def detect_gpu() -> Dict[str, Any]:
    """Detect available GPU hardware using nvidia-smi.

    Returns:
        Dictionary containing GPU detection results with keys:
        - available (bool): True if NVIDIA GPU detected
        - count (int): Number of GPUs found
        - driver (str|None): Driver type (e.g., "nvidia")
        - devices (list): List of device dicts with 'name' and 'memory_mb' keys

    Note:
        Only detects NVIDIA GPUs via nvidia-smi command.
        Gracefully handles cases where nvidia-smi is unavailable.
    """
    gpu_info = {
        "available": False,
        "count": 0,
        "driver": None,
        "devices": [],
    }

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            gpu_info["available"] = True
            gpu_info["driver"] = "nvidia"

            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 2:
                        gpu_info["devices"].append({
                            "name": parts[0],
                            "memory_mb": int(parts[1]),
                        })

            gpu_info["count"] = len(gpu_info["devices"])

    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning(f"GPU detection failed: {e}")
    except subprocess.SubprocessError as e:
        logger.warning(f"GPU detection subprocess error: {e}")
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse nvidia-smi output: {e}")

    return gpu_info


def get_hardware_profile(gpu_info: Dict[str, Any]) -> str:
    """Determine hardware profile based on GPU information.

    Args:
        gpu_info: GPU detection result from detect_gpu() function

    Returns:
        Hardware profile string matching model catalog tiers:
        - cpu_only: No GPU available
        - consumer_8gb: Single GPU with < 8GB VRAM
        - midrange_16gb: Single GPU with 8-23GB VRAM
        - ai_workstation_32gb: Single GPU with 24+GB VRAM
        - ai_workstation_48gb: Dual GPUs
        - multi_gpu_2x40gb: Three or more GPUs
    """
    if not gpu_info["available"]:
        return "cpu_only"

    if gpu_info["count"] == 0:
        return "cpu_only"

    total_vram_mb = sum(d["memory_mb"] for d in gpu_info["devices"])

    if gpu_info["count"] == 1:
        vram_gb = total_vram_mb // 1024
        if vram_gb < 8:
            return "consumer_8gb"
        elif vram_gb < 24:
            return "midrange_16gb"
        else:
            return "ai_workstation_32gb"
    elif gpu_info["count"] == 2:
        return "ai_workstation_48gb"
    else:
        return "multi_gpu_2x40gb"


# =============================================================================
# Model Catalog
# =============================================================================

def load_model_catalog() -> Dict[str, Any]:
    """Load model catalog from hardware-specific configuration file.

    Returns:
        Dictionary containing model recommendations organized by hardware profile.
        Returns empty dict if catalog file not found or cannot be parsed.

    Raises:
        No exceptions raised - all errors are logged and empty dict returned.

    Note:
        Reads from models_by_tier.yaml which contains hardware-specific
        model recommendations for different GPU configurations.
    """
    catalog_path = Path(__file__).parent.parent / "config" / "models_by_tier.yaml"

    if not catalog_path.exists():
        logger.warning(f"Model catalog not found at {catalog_path}")
        return {}

    try:
        with open(catalog_path) as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse model catalog YAML from {catalog_path}: {e}")
        return {}
    except (IOError, PermissionError) as e:
        logger.error(f"Failed to read model catalog from {catalog_path}: {e}")
        return {}


def recommend_models(profile: str, catalog: Dict[str, Any]) -> List[Dict[str, str]]:
    """Recommend models based on detected hardware profile.

    Args:
        profile: Hardware profile string from get_hardware_profile()
        catalog: Model catalog dictionary from load_model_catalog()

    Returns:
        List of model recommendation dictionaries with use case mappings.
        Returns empty list if profile not found in catalog.

    Note:
        Maps internal profile names to catalog keys (e.g., 'cpu_only'
        maps to 'cpu_only_edge' in the catalog).
    """
    profile_key = {
        "cpu_only": "cpu_only_edge",
        "consumer_8gb": "consumer_gpu_8gb",
        "midrange_16gb": "midrange_gpu_16gb",
        "ai_workstation_32gb": "ai_workstation_32gb",
        "ai_workstation_48gb": "ai_workstation_48gb",
        "multi_gpu_2x40gb": "multi_gpu_2x40gb",
    }.get(profile)

    if profile_key and profile_key in catalog:
        return catalog[profile_key].get("use_cases", {})

    return []


# =============================================================================
# Hugging Face MCP Integration
# =============================================================================

async def hf_model_search(
    session: httpx.AsyncClient,
    tier: Optional[str] = None,
    use_case: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search for models via Hugging Face MCP server.

    Args:
        session: httpx async client for HTTP requests
        tier: Optional model tier filter (small, medium, large, specialized)
        use_case: Optional use case filter (orchestrator, coding, utility, etc.)

    Returns:
        List of model dictionaries matching search criteria.
        Returns empty list on HTTP errors.

    Raises:
        No exceptions raised - all errors are logged and empty list returned.

    Note:
        Requires HF MCP server running at http://localhost:8096/healthz
    """
    try:
        response = await session.post(
            "http://localhost:8096/api/model/search",
            json={"tier": tier, "use_case": use_case},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("models", [])
    except httpx.ConnectTimeout as e:
        logger.error(f"HF MCP server connection timeout: {e}")
        return []
    except httpx.ConnectError as e:
        logger.error(f"HF MCP server connection failed: {e}")
        return []
    except httpx.HTTPStatusError as e:
        logger.error(f"HF MCP server returned error status {e.response.status_code}: {e}")
        return []
    except httpx.HTTPError as e:
        logger.error(f"HF MCP search request failed: {e}")
        return []


async def hf_model_download(
    session: httpx.AsyncClient,
    model_id: str,
) -> Dict[str, Any]:
    """Download model via Hugging Face MCP server.

    Args:
        session: httpx async client for HTTP requests
        model_id: Hugging Face model identifier (e.g., 'Qwen/Qwen2.5-7B-Instruct')

    Returns:
        Dictionary with download result containing 'ok' status and
        optional 'error' key on failure.

    Raises:
        No exceptions raised - all errors are logged and error dict returned.

    Note:
        10-minute timeout for large model downloads.
        Requires HF MCP server running at http://localhost:8096/healthz
    """
    try:
        response = await session.post(
            "http://localhost:8096/api/model/download",
            json={"model_id": model_id},
            timeout=600.0,  # 10 minutes
        )
        response.raise_for_status()
        return response.json()
    except httpx.ConnectTimeout as e:
        logger.error(f"Model download connection timeout for {model_id}: {e}")
        return {"ok": False, "error": f"Connection timeout: {e}"}
    except httpx.ConnectError as e:
        logger.error(f"Model download connection failed for {model_id}: {e}")
        return {"ok": False, "error": f"Connection failed: {e}"}
    except httpx.HTTPStatusError as e:
        logger.error(f"Model download HTTP error {e.response.status_code} for {model_id}: {e}")
        return {"ok": False, "error": f"HTTP {e.response.status_code}: {e}"}
    except httpx.HTTPError as e:
        logger.error(f"Model download failed for {model_id}: {e}")
        return {"ok": False, "error": str(e)}


async def hf_list_models(session: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """List cached models via Hugging Face MCP server.

    Args:
        session: httpx async client for HTTP requests

    Returns:
        List of cached model dictionaries with metadata.
        Returns empty list on HTTP errors.

    Raises:
        No exceptions raised - all errors are logged and empty list returned.

    Note:
        Requires HF MCP server running at http://localhost:8096/healthz
    """
    try:
        response = await session.get(
            "http://localhost:8096/api/models",
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("models", [])
    except httpx.ConnectTimeout as e:
        logger.error(f"HF MCP list models connection timeout: {e}")
        return []
    except httpx.ConnectError as e:
        logger.error(f"HF MCP list models connection failed: {e}")
        return []
    except httpx.HTTPStatusError as e:
        logger.error(f"HF MCP list models HTTP error {e.response.status_code}: {e}")
        return []
    except httpx.HTTPError as e:
        logger.error(f"HF MCP list models request failed: {e}")
        return []


# =============================================================================
# TensorZero Config Generation
# =============================================================================

def generate_tensorzero_config(models: List[str]) -> str:
    """Generate TensorZero config fragment for selected models.

    Args:
        models: List of model names to include in config

    Returns:
        TOML-formatted configuration string with model definitions
        for Ollama provider routing.

    Note:
        Only includes models with 'ollama_name' field in catalog.
        Uses 'http://pmoves-ollama:11434/v1' as default API base.
    """
    lines = ["# Auto-generated by hf_model_setup.py", ""]
    ollama_base = "http://pmoves-ollama:11434/v1"

    catalog = load_model_catalog()

    for model_key in models:
        # Find model in catalog
        for tier_name, tier_data in catalog.get("models", {}).items():
            if tier_name == "specialized":
                continue
            for model in tier_data:
                if model["name"] == model_key:
                    ollama_name = model.get("ollama_name")
                    if ollama_name:
                        lines.append(f"[models.{model['name'].replace('-', '_')}]")
                        lines.append('routing = ["ollama_local"]')
                        lines.append("")
                        lines.append(f"[models.{model['name'].replace('-', '_')}.providers.ollama_local]")
                        lines.append('type = "openai"')
                        lines.append(f'api_base = "{ollama_base}"')
                        lines.append(f'model_name = "{ollama_name}"')
                        lines.append('api_key_location = "none"')
                        lines.append("")
                    break

    return "\n".join(lines)


# =============================================================================
# Interactive CLI
# =============================================================================

def print_header(text: str):
    """Print a formatted section header to console.

    Args:
        text: Header text to display

    Side effects:
        Prints formatted header with border to stdout
    """
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_info(text: str):
    """Print an info message to console.

    Args:
        text: Info message to display

    Side effects:
        Prints formatted info message to stdout
    """
    print(f"  ℹ {text}")


def print_success(text: str):
    """Print a success message to console.

    Args:
        text: Success message to display

    Side effects:
        Prints formatted success message to stdout
    """
    print(f"  ✓ {text}")


def print_error(text: str):
    """Print an error message to console.

    Args:
        text: Error message to display

    Side effects:
        Prints formatted error message to stdout
    """
    print(f"  ✗ {text}")


async def interactive_setup():
    """Run interactive model setup workflow.

    Guides users through:
    1. Hardware detection (GPU count, VRAM)
    2. Model catalog loading
    3. Model recommendations based on hardware
    4. HF MCP server availability check
    5. Model download and caching
    6. TensorZero configuration generation
    7. Next steps for deployment

    Side effects:
        - Writes TensorZero config file to working directory
        - Prints progress and recommendations to stdout
        - Makes HTTP requests to HF MCP server

    Note:
        Exits early if HF MCP server is not available.
    """
    print_header("PMOVES.AI Local Model Setup")

    # 1. Hardware Detection
    print("\nStep 1: Detecting hardware...")
    gpu_info = detect_gpu()

    if gpu_info["available"]:
        print_success(f"Found {gpu_info['count']} GPU(s)")
        for device in gpu_info["devices"]:
            print_info(f"  - {device['name']} ({device['memory_mb'] // 1024}GB)")
    else:
        print_info("No GPU detected - CPU-only mode")

    profile = get_hardware_profile(gpu_info)
    print_success(f"Hardware profile: {profile}")

    # 2. Load Model Catalog
    print("\nStep 2: Loading model catalog...")
    catalog = load_model_catalog()
    if catalog:
        print_success("Model catalog loaded")
    else:
        print_error("Failed to load model catalog")
        return

    # 3. Model Recommendations
    print("\nStep 3: Model recommendations for your hardware...")

    tier_configs = {
        "cpu_only_edge": catalog.get("cpu_only_edge", {}),
        "consumer_gpu_8gb": catalog.get("consumer_gpu_8gb", {}),
        "midrange_gpu_16gb": catalog.get("midrange_gpu_16gb", {}),
        "ai_workstation_32gb": catalog.get("ai_workstation_32gb", {}),
        "multi_gpu_2x40gb": catalog.get("multi_gpu_2x40gb", {}),
    }

    tier_config = tier_configs.get(profile, {})
    recommended = tier_config.get("recommended", {})
    use_cases = tier_config.get("use_cases", {})

    if recommended:
        primary = recommended.get("primary", {})
        fallback = recommended.get("fallback", {})
        print_info(f"Primary: {primary.get('name', 'N/A')} ({primary.get('variant', 'N/A')})")
        print_info(f"Fallback: {fallback.get('name', 'N/A')} ({fallback.get('variant', 'N/A')})")

    if use_cases:
        print("\n  Use case recommendations:")
        for use_case, model in use_cases.items():
            print_info(f"  - {use_case}: {model}")

    # 4. Model Selection
    print("\nStep 4: Select models to download")
    print("  Available use cases: orchestrator, builder, coding, utility")

    async with httpx.AsyncClient() as session:
        # Check HF MCP server health
        try:
            response = await session.get("http://localhost:8096/healthz", timeout=5.0)
            if response.status_code == 200:
                print_success("HF MCP server is running")
            else:
                print_info("HF MCP server not responding - starting it...")
                print_info("Run: docker compose -f pmoves/docker-compose/hf-mcp-server.yml up -d")
                return
        except httpx.ConnectTimeout as e:
            logger.warning(f"HF MCP server connection timeout: {e}")
            print_info("HF MCP server not available - starting it...")
            print_info("Run: docker compose -f pmoves/docker-compose/hf-mcp-server.yml up -d")
            return
        except httpx.ConnectError as e:
            logger.warning(f"HF MCP server connection failed: {e}")
            print_info("HF MCP server not available - starting it...")
            print_info("Run: docker compose -f pmoves/docker-compose/hf-mcp-server.yml up -d")
            return
        except httpx.HTTPError as e:
            logger.warning(f"HF MCP server health check failed: {e}")
            print_info("HF MCP server not available - starting it...")
            print_info("Run: docker compose -f pmoves/docker-compose/hf-mcp-server.yml up -d")
            return

        # List cached models
        cached = await hf_list_models(session)
        if cached:
            print_success(f"Found {len(cached)} cached model(s)")
            for model in cached[:5]:
                print_info(f"  - {model['name']}: {model['size_gb']}GB")
        else:
            print_info("No models cached yet")

        # Download models
        print("\nStep 5: Downloading recommended models...")

        to_download = []
        if recommended:
            primary_name = primary.get("name")
            if primary_name:
                to_download.append(primary_name)

        for model_name in to_download:
            print(f"\n  Downloading {model_name}...")
            result = await hf_model_download(session, model_name)
            if result.get("ok"):
                print_success(f"{model_name} downloaded successfully")
            else:
                print_error(f"Failed to download {model_name}: {result.get('error')}")

    # 6. Generate TensorZero Config
    print("\nStep 6: Generating TensorZero configuration...")
    config = generate_tensorzero_config(to_download)

    config_path = Path.cwd() / "tensorzero_local_models.toml"
    try:
        with open(config_path, "w") as f:
            f.write(config)
        print_success(f"Config saved to {config_path}")
    except (IOError, PermissionError) as e:
        print_error(f"Failed to write config to {config_path}: {e}")
        logger.error(f"Config file write failed: {e}")
        return

    # 7. Next Steps
    print_header("Setup Complete!")
    print("\nNext steps:")
    print("  1. Review the generated config: tensorzero_local_models.toml")
    print("  2. Append to your TensorZero config or use as standalone")
    print("  3. Start vLLM services:")
    print("     docker compose -f pmoves/docker-compose/vllm-models.yml --profile medium up -d")
    print("  4. Start BoTZ with local models:")
    print("     cd PMOVES-BoTZ-check && ./scripts/pmoves_botz_ctl.sh start")


def main():
    """Main entry point for interactive model setup.

    Side effects:
        - Runs async interactive setup workflow
        - Handles keyboard interrupts gracefully

    Note:
        Catches KeyboardInterrupt to allow clean exit.
    """
    try:
        asyncio.run(interactive_setup())
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
