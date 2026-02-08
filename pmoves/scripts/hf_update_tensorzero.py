#!/usr/bin/env python3
"""
Generate TensorZero configuration from Hugging Face model catalog.

Reads the model catalog and generates TensorZero TOML configuration
for all models, organized by tier and use case.

Usage:
    python pmoves/scripts/hf_update_tensorzero.py

Output:
    - config/tensorzero/local_models.toml: Model configurations
    - config/tensorzero/botz_function_variants.toml: Function variant mappings
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_catalog() -> Dict:
    """Load model catalog from YAML configuration file.

    Returns:
        Dictionary with 'models' key containing tier-based model lists.

    Raises:
        FileNotFoundError: If catalog file does not exist
        yaml.YAMLError: If catalog file is malformed
        PermissionError: If catalog file cannot be read
        IOError: For other I/O errors
    """
    catalog_path = (
        Path(__file__).parent.parent / "config" / "models.yaml"
    )

    if not catalog_path.exists():
        raise FileNotFoundError(f"Model catalog not found at {catalog_path}")

    try:
        with open(catalog_path) as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse model catalog YAML: {e}")
        raise
    except (PermissionError, IOError) as e:
        logger.error(f"Failed to read model catalog from {catalog_path}: {e}")
        raise


def generate_tensorzero_config(catalog: Dict) -> str:
    """Generate TensorZero TOML configuration from model catalog.

    Args:
        catalog: Dictionary containing models organized by tier
                   (small, medium, large, specialized)

    Returns:
        TOML-formatted configuration string with model definitions
        for Ollama provider routing.

    Note:
        Only includes models with 'ollama_name' field.
        Embedding models are placed in separate 'embedding_models' section.
    """
    lines = [
        "# =============================================================================",
        "# PMOVES.AI Local Model Stack - TensorZero Configuration",
        "# Auto-generated from Hugging Face model catalog",
        "# =============================================================================",
        "",
        "[gateway]",
        'bind_address = "0.0.0.0:3000"',
        "",
        "# =============================================================================",
        "# Ollama Provider (Local GGUF models)",
        "# =============================================================================",
        "",
        "[providers.ollama_local]",
        'type = "openai"',
        'api_base = "http://pmoves-ollama:11434/v1"',
        'api_key_location = "none"',
        "",
        "# For standalone mode (when running separately)",
        "[providers.ollama_standalone]",
        'type = "openai"',
        'api_base = "http://host.docker.internal:11434/v1"',
        'api_key_location = "none"',
        "",
    ]

    # Add models by tier
    models = catalog.get("models", {})

    for tier in ["small", "medium", "large", "specialized"]:
        if tier not in models:
            continue

        lines.append(f"\n# =============================================================================")
        lines.append(f"# {tier.title()} Tier Models")
        lines.append("# =============================================================================")
        lines.append("")

        for model in models[tier]:
            name = model["name"]
            ollama_name = model.get("ollama_name")

            if not ollama_name:
                continue

            toml_name = name.replace("-", "_")
            uses = ", ".join(model.get("uses", []))

            lines.append(f"# {name}")
            if uses:
                lines.append(f"# Uses: {uses}")
            lines.append(f"[models.{toml_name}]")
            lines.append('routing = ["ollama_local"]')
            lines.append("")
            lines.append(f"[models.{toml_name}.providers.ollama_local]")
            lines.append('type = "openai"')
            lines.append(f'model_name = "{ollama_name}"')
            lines.append('api_base = "http://pmoves-ollama:11434/v1"')
            lines.append('api_key_location = "none"')
            lines.append("")

    # Add embedding models
    lines.append("\n# =============================================================================")
    lines.append("# Embedding Models")
    lines.append("# =============================================================================")
    lines.append("")

    for model in models.get("specialized", []):
        if "embedding" in model.get("uses", []):
            name = model["name"]
            ollama_name = model.get("ollama_name")

            if not ollama_name:
                continue

            toml_name = name.replace("-", "_")
            dimensions = model.get("dimensions")

            lines.append(f"[embedding_models.{toml_name}]")
            lines.append('routing = ["ollama_local"]')
            lines.append("")
            lines.append(f"[embedding_models.{toml_name}.providers.ollama_local]")
            lines.append('type = "openai"')
            lines.append(f'model_name = "{ollama_name}"')
            lines.append('api_base = "http://pmoves-ollama:11434/v1"')
            lines.append('api_key_location = "none"')
            if dimensions:
                lines.append(f"# Embedding dimensions: {dimensions}")
            lines.append("")

    return "\n".join(lines)


def generate_function_variants(catalog: Dict) -> str:
    """Generate TensorZero function variants for BoTZ components.

    Args:
        catalog: Dictionary containing models organized by tier

    Returns:
        TOML-formatted configuration string with function variants
        for orchestrator, builder, auditor, coding, utility, and vl_sentinel.

    Note:
        Maps PMOVES.AI BoTZ components to recommended models based on
        hardware tier. Uses weighted variants (1.0, 0.7, 0.5, 0.3)
        for intelligent routing.
    """
    lines = [
        "# =============================================================================",
        "# PMOVES-BoTZ Function Variants - Local Models",
        "# Auto-generated from Hugging Face model catalog",
        "# =============================================================================",
        "",
    ]

    # Component model mappings
    component_mapping = {
        "orchestrator": ["qwen2.5-32b", "qwen2.5-14b", "qwen2.5-7b", "phi3-mini"],
        "builder": ["qwen2.5-14b", "qwen2.5-7b", "llama3.1-8b", "qwen2.5-3b"],
        "auditor": ["qwen2.5-7b", "qwen2.5-3b", "gemma-2-2b", "phi3-mini"],
        "coding": ["qwen2.5-coder-7b", "deepseek-coder-6.7b", "qwen2.5-7b"],
        "utility": ["qwen2.5-3b", "phi3-mini", "gemma-2-2b"],
        "vl_sentinel": ["qwen3-vl-8b", "qwen2-vl-7b"],
    }

    # Build model lookup
    model_lookup = {}
    for tier, models in catalog.get("models", {}).items():
        for model in models:
            model_lookup[model["name"]] = model

    for component, model_names in component_mapping.items():
        lines.append(f"# =============================================================================")
        lines.append(f"# {component.title()} Function")
        lines.append(f"# =============================================================================")
        lines.append("")
        lines.append(f"[functions.{component}]")
        lines.append('type = "chat"')
        lines.append("")

        weights = [1.0, 0.7, 0.5, 0.3]

        for i, model_name in enumerate(model_names):
            if model_name not in model_lookup:
                continue

            model = model_lookup[model_name]
            ollama_name = model.get("ollama_name")
            if not ollama_name:
                continue

            toml_name = model_name.replace("-", "_")
            weight = weights[i] if i < len(weights) else 0.1

            variant = "primary" if i == 0 else f"variant_{i}"

            lines.append(f"[functions.{component}.variants.{variant}]")
            lines.append('type = "chat_completion"')
            lines.append(f'model = "{toml_name}"')
            lines.append(f"weight = {weight}")
            lines.append("")

    return "\n".join(lines)


def main():
    """Main entry point for TensorZero config generation.

    Side effects:
        - Creates config/tensorzero/ directory if needed
        - Writes local_models.toml and botz_function_variants.toml
        - Prints progress and usage instructions to stdout

    Raises:
        SystemExit: On catalog load or file write failures
    """
    print("Loading model catalog...")
    try:
        catalog = load_catalog()
    except (FileNotFoundError, yaml.YAMLError, PermissionError, IOError) as e:
        print(f"Error: Failed to load model catalog - {e}")
        sys.exit(1)

    if not catalog or "models" not in catalog:
        print("Error: Invalid catalog format")
        sys.exit(1)

    print(f"Found {len(catalog.get('models', {}))} model tiers")

    # Generate output
    output_dir = Path(__file__).parent.parent / "config" / "tensorzero"
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except (PermissionError, IOError) as e:
        print(f"Error: Failed to create output directory {output_dir}: {e}")
        sys.exit(1)

    # Full config
    config = generate_tensorzero_config(catalog)
    config_path = output_dir / "local_models.toml"
    try:
        with open(config_path, "w") as f:
            f.write(config)
    except (PermissionError, IOError) as e:
        print(f"Error: Failed to write config to {config_path}: {e}")
        sys.exit(1)

    print(f"✓ Generated {config_path}")

    # Function variants
    variants = generate_function_variants(catalog)
    variants_path = output_dir / "botz_function_variants.toml"
    try:
        with open(variants_path, "w") as f:
            f.write(variants)
    except (PermissionError, IOError) as e:
        print(f"Error: Failed to write variants to {variants_path}: {e}")
        sys.exit(1)

    print(f"✓ Generated {variants_path}")

    print("\nTo use these configurations:")
    print("  1. Copy local_models.toml to your TensorZero config directory")
    print("  2. Append botz_function_variants.toml to your functions config")
    print("  3. Restart TensorZero gateway")


if __name__ == "__main__":
    main()
