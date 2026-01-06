"""
TensorZero Configuration Validators

Provides JSON schema validation and semantic validation for TensorZero TOML configurations.
Ensures configuration integrity before deployment to production systems.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set

from .parser import TensorZeroConfigValidationError

logger = logging.getLogger(__name__)


# ============================================================================
# JSON Schema for TensorZero Configuration
# ============================================================================

CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "TensorZero Configuration",
    "description": "Schema for TensorZero gateway TOML configuration",
    "type": "object",
    "properties": {
        "gateway": {
            "type": "object",
            "properties": {
                "observability": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "async_writes": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "export": {
                    "type": "object",
                    "properties": {
                        "otlp": {
                            "type": "object",
                            "properties": {
                                "traces": {
                                    "type": "object",
                                    "properties": {
                                        "enabled": {"type": "boolean"},
                                        "format": {"type": "string", "enum": ["opentelemetry", "protobuf"]},
                                    },
                                    "additionalProperties": False,
                                },
                            },
                            "additionalProperties": False,
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
        "models": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_-]+$": {
                    "type": "object",
                    "properties": {
                        "routing": {"type": "array", "items": {"type": "string"}},
                        "providers": {
                            "type": "object",
                            "patternProperties": {
                                "^[a-zA-Z0-9_-]+$": {
                                    "type": "object",
                                    "required": ["type", "api_base", "model_name"],
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "enum": ["openai", "anthropic", "vertex", "custom"],
                                        },
                                        "api_base": {"type": "string", "format": "uri"},
                                        "model_name": {"type": "string"},
                                        "api_key_location": {"type": "string"},
                                        "retry": {"type": "boolean"},
                                        "timeout": {"type": "number", "minimum": 0},
                                    },
                                    "additionalProperties": False,
                                },
                            },
                            "additionalProperties": False,
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
        "embedding_models": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_-]+$": {
                    "type": "object",
                    "properties": {
                        "routing": {"type": "array", "items": {"type": "string"}},
                        "providers": {
                            "type": "object",
                            "patternProperties": {
                                "^[a-zA-Z0-9_-]+$": {
                                    "type": "object",
                                    "required": ["type", "api_base", "model_name"],
                                    "properties": {
                                        "type": {"type": "string"},
                                        "api_base": {"type": "string", "format": "uri"},
                                        "model_name": {"type": "string"},
                                        "api_key_location": {"type": "string"},
                                    },
                                    "additionalProperties": False,
                                },
                            },
                            "additionalProperties": False,
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
        "functions": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_-]+$": {
                    "type": "object",
                    "required": ["type"],
                    "properties": {
                        "type": {"type": "string", "enum": ["chat", "json", "dynamic"]},
                        "tools": {"type": "array", "items": {"type": "string"}},
                        "variants": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["name", "type"],
                                "properties": {
                                    "name": {"type": "string", "pattern": "^[a-zA-Z0-9_-]+$"},
                                    "type": {
                                        "type": "string",
                                        "enum": ["chat_completion", "json_completion", "static_weights"],
                                    },
                                    "model": {"type": "string"},
                                    "weight": {"type": "number", "minimum": 0, "maximum": 1},
                                    "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                                    "max_tokens": {"type": "integer", "minimum": 1},
                                },
                                "additionalProperties": False,
                            },
                        },
                        "experimentation": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "candidate_variants": {"type": "object"},
                                "fallback_variants": {"type": "array", "items": {"type": "string"}},
                            },
                            "additionalProperties": False,
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
        "tools": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_-]+$": {
                    "type": "object",
                    "required": ["description"],
                    "properties": {
                        "description": {"type": "string"},
                        "parameters": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}


# ============================================================================
# Valid Provider Types
# ============================================================================

VALID_PROVIDER_TYPES = {"openai", "anthropic", "vertex", "custom", "http", "inline"}


# ============================================================================
# Validation Functions
# ============================================================================

def validate_model_config(model_name: str, model_config: Dict[str, Any]) -> None:
    """
    Validate a model configuration.

    Ensures the model has proper routing and at least one valid provider configuration.

    Args:
        model_name: Name identifier for the model.
        model_config: Dictionary containing model configuration.

    Raises:
        TensorZeroConfigValidationError: If validation fails.
    """
    if not model_config:
        raise TensorZeroConfigValidationError(f"Model '{model_name}' has empty configuration")

    # Check routing configuration
    if "routing" in model_config:
        routing = model_config["routing"]
        if not isinstance(routing, list):
            raise TensorZeroConfigValidationError(
                f"Model '{model_name}' routing must be a list, got {type(routing).__name__}"
            )
        if not routing:
            raise TensorZeroConfigValidationError(
                f"Model '{model_name}' routing list cannot be empty"
            )
        for provider_name in routing:
            if not isinstance(provider_name, str):
                raise TensorZeroConfigValidationError(
                    f"Model '{model_name}' routing entry must be string, got {type(provider_name).__name__}"
                )

    # Check providers configuration
    if "providers" in model_config:
        providers = model_config["providers"]
        if not isinstance(providers, dict):
            raise TensorZeroConfigValidationError(
                f"Model '{model_name}' providers must be a dict, got {type(providers).__name__}"
            )
        if not providers:
            raise TensorZeroConfigValidationError(
                f"Model '{model_name}' must have at least one provider"
            )

        for provider_name, provider_config in providers.items():
            _validate_provider_config(model_name, provider_name, provider_config)

    logger.debug(f"Model '{model_name}' validation passed")


def _validate_provider_config(
    model_name: str,
    provider_name: str,
    provider_config: Dict[str, Any]
) -> None:
    """
    Validate a provider configuration within a model.

    Args:
        model_name: Parent model name.
        provider_name: Provider identifier.
        provider_config: Provider configuration dictionary.

    Raises:
        TensorZeroConfigValidationError: If validation fails.
    """
    if not provider_config:
        raise TensorZeroConfigValidationError(
            f"Model '{model_name}' provider '{provider_name}' has empty configuration"
        )

    # Validate provider type
    provider_type = provider_config.get("type")
    if not provider_type:
        raise TensorZeroConfigValidationError(
            f"Model '{model_name}' provider '{provider_name}' missing required field: type"
        )

    if provider_type not in VALID_PROVIDER_TYPES:
        logger.warning(
            f"Model '{model_name}' provider '{provider_name}' has non-standard type: {provider_type}. "
            f"Valid types: {VALID_PROVIDER_TYPES}"
        )

    # Validate required fields
    required_fields = ["api_base", "model_name"]
    for field in required_fields:
        if field not in provider_config:
            raise TensorZeroConfigValidationError(
                f"Model '{model_name}' provider '{provider_name}' missing required field: {field}"
            )

    # Validate API base format
    api_base = provider_config["api_base"]
    if not isinstance(api_base, str) or not api_base:
        raise TensorZeroConfigValidationError(
            f"Model '{model_name}' provider '{provider_name}' api_base must be a non-empty string"
        )

    # Check if api_base looks like a URL
    if not (api_base.startswith("http://") or api_base.startswith("https://") or
            api_base.startswith("env::")):
        raise TensorZeroConfigValidationError(
            f"Model '{model_name}' provider '{provider_name}' api_base must be a URL or env reference"
        )

    # Validate model name
    model_name_field = provider_config["model_name"]
    if not isinstance(model_name_field, str) or not model_name_field:
        raise TensorZeroConfigValidationError(
            f"Model '{model_name}' provider '{provider_name}' model_name must be a non-empty string"
        )


def validate_function_config(
    function_name: str,
    function_config: Dict[str, Any]
) -> None:
    """
    Validate a function configuration.

    Ensures the function has a valid type and proper variant configuration.

    Args:
        function_name: Name identifier for the function.
        function_config: Dictionary containing function configuration.

    Raises:
        TensorZeroConfigValidationError: If validation fails.
    """
    if not function_config:
        raise TensorZeroConfigValidationError(f"Function '{function_name}' has empty configuration")

    # Validate function type
    function_type = function_config.get("type")
    if not function_type:
        raise TensorZeroConfigValidationError(
            f"Function '{function_name}' missing required field: type"
        )

    valid_function_types = {"chat", "json", "dynamic"}
    if function_type not in valid_function_types:
        raise TensorZeroConfigValidationError(
            f"Function '{function_name}' has invalid type: {function_type}. "
            f"Valid types: {valid_function_types}"
        )

    # Validate tools if present
    if "tools" in function_config:
        tools = function_config["tools"]
        if not isinstance(tools, list):
            raise TensorZeroConfigValidationError(
                f"Function '{function_name}' tools must be a list, got {type(tools).__name__}"
            )

    # Validate variants if present
    if "variants" in function_config:
        variants = function_config["variants"]
        if not isinstance(variants, list):
            raise TensorZeroConfigValidationError(
                f"Function '{function_name}' variants must be a list, got {type(variants).__name__}"
            )

        # Check for duplicate variant names
        variant_names: Set[str] = set()
        for variant in variants:
            if not isinstance(variant, dict):
                raise TensorZeroConfigValidationError(
                    f"Function '{function_name}' variant must be a dict"
                )
            variant_name = variant.get("name")
            if not variant_name:
                raise TensorZeroConfigValidationError(
                    f"Function '{function_name}' has variant missing 'name' field"
                )
            if variant_name in variant_names:
                raise TensorZeroConfigValidationError(
                    f"Function '{function_name}' has duplicate variant name: {variant_name}"
                )
            variant_names.add(variant_name)

    logger.debug(f"Function '{function_name}' validation passed")


def validate_variant_config(
    variant_name: str,
    variant_config: Dict[str, Any],
    function_config: Dict[str, Any]
) -> None:
    """
    Validate a variant configuration within a function.

    Ensures the variant references a valid model and has proper configuration.

    Args:
        variant_name: Name identifier for the variant.
        variant_config: Dictionary containing variant configuration.
        function_config: Parent function configuration (for context).

    Raises:
        TensorZeroConfigValidationError: If validation fails.
    """
    if not variant_config:
        raise TensorZeroConfigValidationError(f"Variant '{variant_name}' has empty configuration")

    # Validate variant type
    variant_type = variant_config.get("type")
    if not variant_type:
        raise TensorZeroConfigValidationError(
            f"Variant '{variant_name}' missing required field: type"
        )

    valid_variant_types = {"chat_completion", "json_completion", "static_weights"}
    if variant_type not in valid_variant_types:
        raise TensorZeroConfigValidationError(
            f"Variant '{variant_name}' has invalid type: {variant_type}. "
            f"Valid types: {valid_variant_types}"
        )

    # Validate model reference (except for static_weights which may not have direct model)
    if variant_type != "static_weights":
        model_ref = variant_config.get("model")
        if not model_ref:
            raise TensorZeroConfigValidationError(
                f"Variant '{variant_name}' missing required field: model"
            )
        if not isinstance(model_ref, str) or not model_ref:
            raise TensorZeroConfigValidationError(
                f"Variant '{variant_name}' model must be a non-empty string"
            )

    # Validate weight if present
    if "weight" in variant_config:
        weight = variant_config["weight"]
        if not isinstance(weight, (int, float)):
            raise TensorZeroConfigValidationError(
                f"Variant '{variant_name}' weight must be a number, got {type(weight).__name__}"
            )
        if not (0 <= weight <= 1):
            raise TensorZeroConfigValidationError(
                f"Variant '{variant_name}' weight must be between 0 and 1, got {weight}"
            )

    # Validate temperature if present
    if "temperature" in variant_config:
        temperature = variant_config["temperature"]
        if not isinstance(temperature, (int, float)):
            raise TensorZeroConfigValidationError(
                f"Variant '{variant_name}' temperature must be a number, got {type(temperature).__name__}"
            )
        if not (0 <= temperature <= 2):
            raise TensorZeroConfigValidationError(
                f"Variant '{variant_name}' temperature must be between 0 and 2, got {temperature}"
            )

    logger.debug(f"Variant '{variant_name}' validation passed")


# ============================================================================
# Cross-Reference Validation
# ============================================================================

def validate_cross_references(config: Dict[str, Any]) -> None:
    """
    Validate cross-references between configuration sections.

    Ensures that variants reference existing models, functions reference existing tools, etc.

    Args:
        config: Full configuration dictionary.

    Raises:
        TensorZeroConfigValidationError: If cross-references are invalid.
    """
    models = set(config.get("models", {}).keys())
    embedding_models = set(config.get("embedding_models", {}).keys())
    all_models = models | embedding_models

    tools = set(config.get("tools", {}).keys())

    # Validate function variants reference existing models
    functions = config.get("functions", {})
    for function_name, function_config in functions.items():
        variants = function_config.get("variants", [])
        for variant in variants:
            variant_name = variant.get("name", "unnamed")
            model_ref = variant.get("model")

            if model_ref and model_ref not in all_models:
                raise TensorZeroConfigValidationError(
                    f"Function '{function_name}' variant '{variant_name}' references "
                    f"non-existent model: {model_ref}. "
                    f"Available models: {sorted(all_models)}"
                )

        # Validate function tools reference existing tools
        function_tools = function_config.get("tools", [])
        for tool_ref in function_tools:
            if tool_ref not in tools:
                raise TensorZeroConfigValidationError(
                    f"Function '{function_name}' references non-existent tool: {tool_ref}. "
                    f"Available tools: {sorted(tools)}"
                )

    logger.info("Cross-reference validation passed")


# ============================================================================
# Name Validation Utilities
# ============================================================================

def validate_identifier_name(name: str, entity_type: str = "identifier") -> None:
    """
    Validate that a name is a valid identifier.

    Valid identifiers contain only alphanumeric characters, underscores, and hyphens.

    Args:
        name: The name to validate.
        entity_type: Type of entity for error messages.

    Raises:
        TensorZeroConfigValidationError: If the name is invalid.
    """
    if not name:
        raise TensorZeroConfigValidationError(f"{entity_type} name cannot be empty")

    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise TensorZeroConfigValidationError(
            f"{entity_type} name '{name}' contains invalid characters. "
            "Only alphanumeric, underscore, and hyphen are allowed."
        )

    if len(name) > 128:
        raise TensorZeroConfigValidationError(
            f"{entity_type} name '{name}' is too long (max 128 characters)"
        )


def validate_config_path(config_path: str) -> None:
    """
    Validate that a configuration path is safe and within expected bounds.

    Prevents path traversal attacks and ensures file is within expected directory.

    Args:
        config_path: Path to the configuration file.

    Raises:
        TensorZeroConfigValidationError: If the path is invalid or unsafe.
    """
    if not config_path:
        raise TensorZeroConfigValidationError("Configuration path cannot be empty")

    # Check for path traversal attempts
    if "../" in config_path or config_path.startswith("/"):
        raise TensorZeroConfigValidationError(
            f"Configuration path '{config_path}' contains unsafe path traversal"
        )

    # Must end with .toml extension
    if not config_path.endswith(".toml"):
        raise TensorZeroConfigValidationError(
            f"Configuration path '{config_path}' must have .toml extension"
        )
