#!/usr/bin/env python3
"""
TensorZero CLI - Dynamic configuration management tool.

This CLI provides commands for managing TensorZero gateway configurations,
including validation, variant management, hot reload, and template application.

Usage:
    tz validate <config_path>
    tz get-config
    tz add-variant <function> <variant>
    tz reload [--create-backup]
    tz apply-template <template> <function>
"""

import click
import json
import re
import sys
from pathlib import Path
from typing import Optional
import toml
import httpx
from datetime import datetime


# ============================================================================
# Path Security Validation
# ============================================================================

# Valid name pattern for templates, functions, variants
VALID_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

# Allowed file extensions
ALLOWED_CONFIG_EXTENSIONS = {'.toml'}
ALLOWED_TEMPLATE_EXTENSIONS = {'.json'}


def validate_config_path(path: Path, must_exist: bool = False) -> Path:
    """
    Validate that a configuration path is safe and within expected bounds.

    Prevents path traversal attacks by ensuring the resolved path is within
    the expected directory structure.

    Args:
        path: Path to validate
        must_exist: Whether the path must exist

    Returns:
        The validated, resolved absolute path

    Raises:
        ValueError: If the path is unsafe or invalid
    """
    if not path:
        raise ValueError("Path cannot be empty")

    # Resolve to absolute path
    try:
        resolved = path.resolve()
    except Exception as e:
        raise ValueError(f"Invalid path '{path}': {e}")

    # Check for path traversal (should not go above current directory if relative)
    if str(path).startswith('../') or '/..' in str(path):
        raise ValueError(f"Path traversal not allowed: '{path}'")

    # Validate file extension if it has one
    if resolved.suffix and resolved.suffix not in ALLOWED_CONFIG_EXTENSIONS:
        raise ValueError(
            f"Invalid config file extension: {resolved.suffix}. "
            f"Allowed: {ALLOWED_CONFIG_EXTENSIONS}"
        )

    # Check existence if required
    if must_exist and not resolved.exists():
        raise ValueError(f"Configuration file not found: {resolved}")

    return resolved


def validate_template_name(name: str) -> str:
    """
    Validate a template or function name for safety.

    Args:
        name: Name to validate

    Returns:
        The validated name

    Raises:
        ValueError: If the name contains invalid characters
    """
    if not name:
        raise ValueError("Name cannot be empty")

    if not VALID_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid name '{name}'. Only alphanumeric, underscore, and hyphen are allowed."
        )

    return name


def validate_safe_path(base_dir: Path, user_path: str, allowed_extensions: set) -> Path:
    """
    Validate that a user-provided path is safe within a base directory.

    Args:
        base_dir: Base directory that the path must be within
        user_path: User-provided path component
        allowed_extensions: Set of allowed file extensions

    Returns:
        The validated, safe path

    Raises:
        ValueError: If the path is unsafe
    """
    if not user_path:
        raise ValueError("Path cannot be empty")

    # Check for path traversal in user input
    if '..' in user_path or user_path.startswith('/') or user_path.startswith('\\'):
        raise ValueError(f"Unsafe path: '{user_path}'")

    # Construct full path
    full_path = (base_dir / user_path).resolve()

    # Ensure the resolved path is within base directory
    try:
        full_path.relative_to(base_dir.resolve())
    except ValueError:
        raise ValueError(f"Path '{user_path}' is outside allowed directory")

    # Validate extension
    if full_path.suffix and full_path.suffix not in allowed_extensions:
        raise ValueError(
            f"Invalid file extension: {full_path.suffix}. "
            f"Allowed: {allowed_extensions}"
        )

    return full_path


# ============================================================================
# Configuration
# ============================================================================

# Default paths (will be validated before use)
DEFAULT_CONFIG_PATH = Path("pmoves/tensorzero/config/tensorzero.toml")
TEMPLATES_DIR = Path("pmoves/tensorzero/templates")
VARIANTS_DIR = TEMPLATES_DIR / "variants"
FUNCTIONS_DIR = TEMPLATES_DIR / "functions"
BACKUP_DIR = Path("pmoves/tensorzero/config/backups")

# TensorZero Gateway API
GATEWAY_URL = "http://localhost:3030"


def success_msg(msg: str):
    """Print success message with checkmark."""
    click.echo(f"✅ {msg}")


def error_msg(msg: str):
    """Print error message with cross mark."""
    click.echo(f"❌ {msg}", err=True)


def info_msg(msg: str):
    """Print info message."""
    click.echo(f"ℹ️  {msg}")


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """
    TensorZero CLI - Manage TensorZero gateway configurations.

    This tool provides commands for:
    - Validating configuration files
    - Managing model variants
    - Triggering hot reloads
    - Applying smart templates
    - Testing configuration changes

    For help on specific commands, run:
        tz <command> --help
    """
    pass


@cli.command()
@click.argument("config_path", type=click.Path(exists=True), required=False)
def validate(config_path: Optional[str]):
    """
    Validate TensorZero configuration file.

    CONFIG_PATH: Path to tensorzero.toml file (default: pmoves/tensorzero/config/tensorzero.toml)

    Example:
        tz validate
        tz validate /path/to/custom/tensorzero.toml
    """
    if not config_path:
        config_path = str(DEFAULT_CONFIG_PATH)

    try:
        config_file = validate_config_path(Path(config_path), must_exist=True)
    except ValueError as e:
        error_msg(str(e))
        sys.exit(1)

    info_msg(f"Validating configuration: {config_file}")

    try:
        config = toml.load(config_file)

        # Check for required sections
        if "gateway" not in config:
            error_msg("Missing required [gateway] section")
            sys.exit(1)

        # Validate models section
        if "models" in config:
            model_count = len(config["models"])
            info_msg(f"Found {model_count} chat models")

        # Validate embedding models
        if "embedding_models" in config:
            embed_count = len(config["embedding_models"])
            info_msg(f"Found {embed_count} embedding models")

        # Validate functions
        if "functions" in config:
            func_count = len(config["functions"])
            info_msg(f"Found {func_count} functions")

        success_msg("Configuration is valid!")
        sys.exit(0)

    except Exception as e:
        error_msg(f"Validation failed: {e}")
        sys.exit(1)


@cli.command()
def get_config():
    """
    Display current TensorZero configuration.

    Shows the parsed configuration in JSON format for easy reading.

    Example:
        tz get-config
    """
    if not DEFAULT_CONFIG_PATH.exists():
        error_msg(f"Configuration file not found: {DEFAULT_CONFIG_PATH}")
        sys.exit(1)

    try:
        config = toml.load(DEFAULT_CONFIG_PATH)

        # Display configuration in JSON format
        click.echo(json.dumps(config, indent=2))

        success_msg("Configuration retrieved successfully")

    except Exception as e:
        error_msg(f"Failed to read configuration: {e}")
        sys.exit(1)


@cli.command()
@click.argument("function_name")
@click.argument("variant_name")
@click.option("--weight", type=float, default=1.0, help="Variant weight (default: 1.0)")
@click.option("--model", type=str, required=True, help="Model name to use")
def add_variant(function_name: str, variant_name: str, weight: float, model: str):
    """
    Add a new variant to a function.

    FUNCTION_NAME: Name of the function to modify
    VARIANT_NAME: Name of the variant to add

    Example:
        tz add-variant orchestrator fast_variant --model qwen2_5_14b --weight 0.5
    """
    # Validate function and variant names
    try:
        function_name = validate_template_name(function_name)
        variant_name = validate_template_name(variant_name)
        config_path = validate_config_path(DEFAULT_CONFIG_PATH, must_exist=True)
    except ValueError as e:
        error_msg(str(e))
        sys.exit(1)

    try:
        config = toml.load(config_path)

        # Initialize functions section if needed
        if "functions" not in config:
            config["functions"] = {}

        # Initialize function if needed
        if function_name not in config["functions"]:
            config["functions"][function_name] = {}
            config["functions"][function_name]["variants"] = {}

        # Add variant
        variant_key = f"variants.{variant_name}"
        config["functions"][function_name][variant_key] = {
            "type": "basic",
            "weight": weight,
            "model": model
        }

        # Write back to file
        with open(config_path, "w") as f:
            toml.dump(config, f)

        success_msg(f"Added variant '{variant_name}' to function '{function_name}'")
        info_msg(f"Model: {model}, Weight: {weight}")

    except Exception as e:
        error_msg(f"Failed to add variant: {e}")
        sys.exit(1)


@cli.command()
@click.argument("function_name")
@click.argument("variant_name")
@click.option("--weight", type=float, help="Update variant weight")
@click.option("--model", type=str, help="Update model name")
def update_variant(function_name: str, variant_name: str, weight: Optional[float], model: Optional[str]):
    """
    Update an existing variant in a function.

    FUNCTION_NAME: Name of the function
    VARIANT_NAME: Name of the variant to update

    Example:
        tz update-variant orchestrator fast_variant --weight 0.8
        tz update-variant orchestrator fast_variant --model qwen2_5_32b
    """
    if not DEFAULT_CONFIG_PATH.exists():
        error_msg(f"Configuration file not found: {DEFAULT_CONFIG_PATH}")
        sys.exit(1)

    if not weight and not model:
        error_msg("Must specify at least --weight or --model to update")
        sys.exit(1)

    try:
        config = toml.load(DEFAULT_CONFIG_PATH)

        # Check if function exists
        if "functions" not in config or function_name not in config["functions"]:
            error_msg(f"Function '{function_name}' not found")
            sys.exit(1)

        variant_key = f"variants.{variant_name}"
        if variant_key not in config["functions"][function_name]:
            error_msg(f"Variant '{variant_name}' not found in function '{function_name}'")
            sys.exit(1)

        # Update variant
        if weight:
            config["functions"][function_name][variant_key]["weight"] = weight
        if model:
            config["functions"][function_name][variant_key]["model"] = model

        # Write back to file
        with open(DEFAULT_CONFIG_PATH, "w") as f:
            toml.dump(config, f)

        success_msg(f"Updated variant '{variant_name}' in function '{function_name}'")

    except Exception as e:
        error_msg(f"Failed to update variant: {e}")
        sys.exit(1)


@cli.command()
@click.argument("function_name")
@click.argument("variant_name")
def remove_variant(function_name: str, variant_name: str):
    """
    Remove a variant from a function.

    FUNCTION_NAME: Name of the function
    VARIANT_NAME: Name of the variant to remove

    Example:
        tz remove-variant orchestrator fast_variant
    """
    if not DEFAULT_CONFIG_PATH.exists():
        error_msg(f"Configuration file not found: {DEFAULT_CONFIG_PATH}")
        sys.exit(1)

    try:
        config = toml.load(DEFAULT_CONFIG_PATH)

        # Check if function exists
        if "functions" not in config or function_name not in config["functions"]:
            error_msg(f"Function '{function_name}' not found")
            sys.exit(1)

        variant_key = f"variants.{variant_name}"
        if variant_key not in config["functions"][function_name]:
            error_msg(f"Variant '{variant_name}' not found in function '{function_name}'")
            sys.exit(1)

        # Remove variant
        del config["functions"][function_name][variant_key]

        # Write back to file
        with open(DEFAULT_CONFIG_PATH, "w") as f:
            toml.dump(config, f)

        success_msg(f"Removed variant '{variant_name}' from function '{function_name}'")

    except Exception as e:
        error_msg(f"Failed to remove variant: {e}")
        sys.exit(1)


@cli.command()
@click.option("--create-backup", is_flag=True, help="Create backup before reload")
def reload(create_backup: bool):
    """
    Trigger hot reload of TensorZero configuration.

    Signals the TensorZero gateway to reload its configuration.

    Example:
        tz reload
        tz reload --create-backup
    """
    if create_backup:
        # Create backup
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"tensorzero.toml.{timestamp}"

        try:
            import shutil
            shutil.copy2(DEFAULT_CONFIG_PATH, backup_path)
            success_msg(f"Backup created: {backup_path}")
        except Exception as e:
            error_msg(f"Failed to create backup: {e}")
            sys.exit(1)

    # Trigger reload via API
    try:
        response = httpx.post(f"{GATEWAY_URL}/admin/reload", timeout=10.0)

        if response.status_code == 200:
            success_msg("Configuration reloaded successfully")
        else:
            error_msg(f"Reload failed with status {response.status_code}: {response.text}")
            sys.exit(1)

    except httpx.ConnectError:
        error_msg(f"Cannot connect to TensorZero gateway at {GATEWAY_URL}")
        info_msg("Make sure the gateway is running")
        sys.exit(1)
    except Exception as e:
        error_msg(f"Failed to trigger reload: {e}")
        sys.exit(1)


@cli.command()
@click.argument("backup_name", required=False)
def rollback(backup_name: Optional[str]):
    """
    Rollback to a previous configuration version.

    BACKUP_NAME: Name of backup file (default: most recent)

    Example:
        tz rollback
        tz rollback tensorzero.toml.20251226_120000
    """
    if not BACKUP_DIR.exists():
        error_msg("No backups found")
        sys.exit(1)

    # Find backups
    backups = sorted(BACKUP_DIR.glob("tensorzero.toml.*"), reverse=True)

    if not backups:
        error_msg("No backups found")
        sys.exit(1)

    # Select backup
    if backup_name:
        backup_path = BACKUP_DIR / backup_name
        if not backup_path.exists():
            error_msg(f"Backup not found: {backup_name}")
            sys.exit(1)
    else:
        backup_path = backups[0]
        info_msg(f"Using most recent backup: {backup_path.name}")

    try:
        import shutil
        shutil.copy2(backup_path, DEFAULT_CONFIG_PATH)
        success_msg(f"Rolled back to: {backup_path.name}")
        info_msg("Run 'tz reload' to apply the rollback")

    except Exception as e:
        error_msg(f"Failed to rollback: {e}")
        sys.exit(1)


@cli.command()
@click.argument("function_name")
@click.option("--count", type=int, default=5, help="Number of test calls (default: 5)")
@click.option("--input", type=str, default="test", help="Test input data (default: 'test')")
def test(function_name: str, count: int, input: str):
    """
    Test a function with sample requests.

    FUNCTION_NAME: Name of the function to test

    Example:
        tz test orchestrator --count 10
        tz test orchestrator --input '{"context": "test context"}'
    """
    info_msg(f"Testing function '{function_name}' with {count} requests...")

    try:
        # Parse input as JSON if it looks like JSON
        test_input = input
        if input.startswith("{"):
            test_input = json.loads(input)

        success_count = 0
        total_count = count

        for i in range(count):
            try:
                response = httpx.post(
                    f"{GATEWAY_URL}/v1/functions/{function_name}",
                    json={"input": test_input},
                    timeout=30.0
                )

                if response.status_code == 200:
                    success_count += 1
                    click.echo(f"✅ Request {i+1}/{count}: Success")
                else:
                    click.echo(f"❌ Request {i+1}/{count}: Failed (status {response.status_code})")

            except Exception as e:
                click.echo(f"❌ Request {i+1}/{count}: Error - {e}")

        # Summary
        click.echo()
        success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
        info_msg(f"Test Summary: {success_count}/{total_count} successful ({success_rate:.1f}%)")

        if success_count == total_count:
            success_msg("All tests passed!")
        else:
            error_msg(f"{total_count - success_count} tests failed")

    except Exception as e:
        error_msg(f"Test failed: {e}")
        sys.exit(1)


@cli.command()
def history():
    """
    Show configuration change history.

    Lists all backup files with timestamps.

    Example:
        tz history
    """
    if not BACKUP_DIR.exists():
        info_msg("No backups found")
        return

    backups = sorted(BACKUP_DIR.glob("tensorzero.toml.*"), reverse=True)

    if not backups:
        info_msg("No backups found")
        return

    click.echo()
    click.echo("Configuration History:")
    click.echo("=" * 60)

    for backup in backups:
        # Extract timestamp from filename
        timestamp_str = backup.name.replace("tensorzero.toml.", "")
        try:
            timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            click.echo(f"  📅 {timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {backup.name}")
        except:
            click.echo(f"  📄 {backup.name}")

    click.echo()


@cli.command()
@click.argument("template_name")
@click.argument("function_name")
def apply_template(template_name: str, function_name: str):
    """
    Apply a smart default template to create or update a function.

    TEMPLATE_NAME: Name of the template to apply
                   Variants: low_latency, high_quality, cost_optimized, hybrid_fallback, ab_test
                   Functions: agent_orchestrator, knowledge_retrieval, code_generation, media_processor

    FUNCTION_NAME: Name of the function to create/update

    Examples:
        tz apply-template low_latency my_function
        tz apply-template agent_orchestrator orchestrator
    """
    # Validate template name
    try:
        template_name = validate_template_name(template_name)
        function_name = validate_template_name(function_name)
        config_path = validate_config_path(DEFAULT_CONFIG_PATH, must_exist=True)
    except ValueError as e:
        error_msg(str(e))
        sys.exit(1)

    # Try variant templates first
    variant_template = VARIANTS_DIR / f"{template_name}.json"
    function_template = FUNCTIONS_DIR / f"{template_name}.json"

    template_path = None
    template_type = None

    if variant_template.exists():
        template_path = variant_template
        template_type = "variant"
    elif function_template.exists():
        template_path = function_template
        template_type = "function"
    else:
        error_msg(f"Template not found: {template_name}")
        info_msg("Available templates:")
        info_msg("  Variants: low_latency, high_quality, cost_optimized, hybrid_fallback, ab_test")
        info_msg("  Functions: agent_orchestrator, knowledge_retrieval, code_generation, media_processor")
        sys.exit(1)

    try:
        with open(template_path, "r") as f:
            template = json.load(f)

        config = toml.load(config_path)

        # Initialize functions section if needed
        if "functions" not in config:
            config["functions"] = {}

        if template_type == "variant":
            # Apply variant template
            if function_name not in config["functions"]:
                config["functions"][function_name] = {}
                config["functions"][function_name]["variants"] = {}

            # Add variants from template
            for variant_name, variant_config in template.get("variants", {}).items():
                variant_key = f"variants.{variant_name}"
                config["functions"][function_name][variant_key] = variant_config

            success_msg(f"Applied variant template '{template_name}' to function '{function_name}'")

        elif template_type == "function":
            # Apply full function template
            config["functions"][function_name] = template
            success_msg(f"Applied function template '{template_name}' as '{function_name}'")

        # Write back to file
        with open(config_path, "w") as f:
            toml.dump(config, f)

        info_msg(f"Description: {template.get('description', 'N/A')}")

    except Exception as e:
        error_msg(f"Failed to apply template: {e}")
        sys.exit(1)


@cli.command()
def list_templates():
    """
    List all available templates.

    Shows available variant and function templates with descriptions.

    Example:
        tz list-templates
    """
    click.echo()
    click.echo("Available Templates:")
    click.echo("=" * 80)

    # Variant templates
    click.echo("\n📦 Variant Templates:")
    for template_file in sorted(VARIANTS_DIR.glob("*.json")):
        try:
            with open(template_file, "r") as f:
                template = json.load(f)
            name = template_file.stem
            description = template.get("description", "No description")
            click.echo(f"  • {name}: {description}")
        except:
            click.echo(f"  • {template_file.stem}: (error reading template)")

    # Function templates
    click.echo("\n⚙️  Function Templates:")
    for template_file in sorted(FUNCTIONS_DIR.glob("*.json")):
        try:
            with open(template_file, "r") as f:
                template = json.load(f)
            name = template_file.stem
            description = template.get("description", "No description")
            click.echo(f"  • {name}: {description}")
        except:
            click.echo(f"  • {template_file.stem}: (error reading template)")

    click.echo()


if __name__ == "__main__":
    cli()
