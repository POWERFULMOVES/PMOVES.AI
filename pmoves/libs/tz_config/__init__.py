"""
TensorZero Configuration Management Library

Provides utilities for parsing, validating, and updating TensorZero TOML configurations.
Supports hot reload, backup/rollback, and comprehensive validation rules.
"""

from .parser import TensorZeroConfig
from .validators import validate_model_config, validate_function_config, validate_variant_config

__all__ = [
    "TensorZeroConfig",
    "validate_model_config",
    "validate_function_config",
    "validate_variant_config",
]

__version__ = "0.1.0"
