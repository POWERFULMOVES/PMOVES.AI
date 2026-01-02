"""
TensorZero TOML Configuration Parser

Provides robust parsing, validation, and manipulation of TensorZero TOML configurations.
Supports backup/rollback, atomic updates, and comprehensive error handling.
"""

import copy
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import toml
from jsonschema import validate, ValidationError as JsonSchemaValidationError

from .validators import (
    CONFIG_SCHEMA,
    validate_model_config,
    validate_function_config,
    validate_variant_config,
)

logger = logging.getLogger(__name__)


class TensorZeroConfigError(Exception):
    """Base exception for TensorZero configuration errors."""

    pass


class TensorZeroConfigValidationError(TensorZeroConfigError):
    """Raised when configuration validation fails."""

    pass


class TensorZeroConfigParseError(TensorZeroConfigError):
    """Raised when TOML parsing fails."""

    pass


class TensorZeroConfig:
    """
    TensorZero configuration manager with parsing, validation, and manipulation capabilities.

    This class provides a high-level interface for working with TensorZero TOML configurations,
    including validation, updates, backup, and rollback functionality.

    Attributes:
        config_path: Path to the TensorZero TOML configuration file.
        config: Dictionary containing the parsed configuration.
        backup_dir: Directory for storing configuration backups.
        max_backups: Maximum number of backups to retain.

    Example:
        >>> config = TensorZeroConfig("/path/to/tensorzero.toml")
        >>> config.load()
        >>> config.update_function("my_function", {"variants": [{"name": "variant1"}]})
        >>> config.save()
    """

    def __init__(
        self,
        config_path: str,
        backup_dir: Optional[str] = None,
        max_backups: int = 10,
    ):
        """
        Initialize TensorZero configuration manager.

        Args:
            config_path: Path to the TensorZero TOML configuration file.
            backup_dir: Directory for storing configuration backups. Defaults to
                config_path.backup in the same directory as the config file.
            max_backups: Maximum number of backups to retain. Oldest backups are
                deleted when this limit is exceeded.

        Raises:
            TensorZeroConfigError: If config_path does not exist.
        """
        self.config_path = Path(config_path).resolve()

        if not self.config_path.exists():
            raise TensorZeroConfigError(f"Configuration file not found: {config_path}")

        self.config: Dict[str, Any] = {}
        self.backup_dir = Path(backup_dir) if backup_dir else self.config_path.parent / "config_backup"
        self.max_backups = max_backups

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initialized TensorZeroConfig manager for {self.config_path}")

    def _load_toml(self) -> Dict[str, Any]:
        """
        Load and parse the TOML configuration file.

        Returns:
            Parsed configuration as a dictionary.

        Raises:
            TensorZeroConfigParseError: If TOML parsing fails.
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = toml.load(f)
            logger.debug(f"Successfully loaded TOML from {self.config_path}")
            return config
        except toml.TomlDecodeError as e:
            error_msg = f"Failed to parse TOML file {self.config_path}: {e}"
            logger.error(error_msg)
            raise TensorZeroConfigParseError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to load configuration file {self.config_path}: {e}"
            logger.error(error_msg)
            raise TensorZeroConfigError(error_msg) from e

    def load(self) -> "TensorZeroConfig":
        """
        Load the configuration from disk and validate it.

        Returns:
            Self for method chaining.

        Raises:
            TensorZeroConfigParseError: If TOML parsing fails.
            TensorZeroConfigValidationError: If validation fails.
        """
        logger.info(f"Loading configuration from {self.config_path}")
        self.config = self._load_toml()
        self.validate()
        logger.info("Configuration loaded and validated successfully")
        return self

    def validate(self) -> bool:
        """
        Validate the current configuration against TensorZero schema rules.

        Returns:
            True if validation passes.

        Raises:
            TensorZeroConfigValidationError: If validation fails with detailed error messages.
        """
        logger.debug("Validating configuration...")

        # Validate against JSON schema
        try:
            validate(instance=self.config, schema=CONFIG_SCHEMA)
            logger.debug("JSON schema validation passed")
        except JsonSchemaValidationError as e:
            error_msg = f"Schema validation failed: {e.message} at path {'.'.join(str(p) for p in e.path)}"
            logger.error(error_msg)
            raise TensorZeroConfigValidationError(error_msg) from e

        # Validate models
        if "models" in self.config:
            for model_name, model_config in self.config["models"].items():
                try:
                    validate_model_config(model_name, model_config)
                except TensorZeroConfigValidationError as e:
                    logger.error(f"Model validation failed for {model_name}: {e}")
                    raise

        # Validate functions and variants
        if "functions" in self.config:
            for function_name, function_config in self.config["functions"].items():
                try:
                    validate_function_config(function_name, function_config)
                except TensorZeroConfigValidationError as e:
                    logger.error(f"Function validation failed for {function_name}: {e}")
                    raise

                # Validate variants
                if "variants" in function_config:
                    for variant in function_config["variants"]:
                        try:
                            variant_name = variant.get("name", "unnamed")
                            validate_variant_config(variant_name, variant, function_config)
                        except TensorZeroConfigValidationError as e:
                            logger.error(f"Variant validation failed for {variant_name}: {e}")
                            raise

        logger.info("Configuration validation passed")
        return True

    def save(self, create_backup: bool = True) -> None:
        """
        Save the current configuration to disk, optionally creating a backup.

        Args:
            create_backup: If True, create a backup before saving.

        Raises:
            TensorZeroConfigError: If save operation fails.
        """
        if create_backup:
            self._create_backup()

        try:
            # Write to temporary file first for atomicity
            temp_path = self.config_path.with_suffix(".toml.tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                toml.dump(self.config, f)

            # Atomic rename
            temp_path.replace(self.config_path)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            error_msg = f"Failed to save configuration to {self.config_path}: {e}"
            logger.error(error_msg)
            raise TensorZeroConfigError(error_msg) from e

    def _create_backup(self) -> Path:
        """
        Create a timestamped backup of the current configuration file.

        Returns:
            Path to the created backup file.

        Raises:
            TensorZeroConfigError: If backup creation fails.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{self.config_path.stem}_{timestamp}.toml"
        backup_path = self.backup_dir / backup_filename

        try:
            shutil.copy2(self.config_path, backup_path)
            logger.info(f"Created backup at {backup_path}")

            # Clean old backups
            self._cleanup_old_backups()

            return backup_path
        except Exception as e:
            error_msg = f"Failed to create backup at {backup_path}: {e}"
            logger.error(error_msg)
            raise TensorZeroConfigError(error_msg) from e

    def _cleanup_old_backups(self) -> None:
        """
        Remove oldest backups if max_backups limit is exceeded.

        Keeps the most recent max_backups backups sorted by modification time.
        """
        backups = sorted(
            self.backup_dir.glob(f"{self.config_path.stem}_*.toml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if len(backups) > self.max_backups:
            old_backups = backups[self.max_backups :]
            for old_backup in old_backups:
                try:
                    old_backup.unlink()
                    logger.debug(f"Removed old backup: {old_backup}")
                except Exception as e:
                    logger.warning(f"Failed to remove old backup {old_backup}: {e}")

    def rollback(self, backup_filename: Optional[str] = None) -> None:
        """
        Rollback to a previous configuration backup.

        Args:
            backup_filename: Specific backup file to restore. If None, restores
                the most recent backup.

        Raises:
            TensorZeroConfigError: If rollback fails or backup not found.
        """
        if backup_filename:
            backup_path = self.backup_dir / backup_filename
        else:
            # Find most recent backup
            backups = sorted(
                self.backup_dir.glob(f"{self.config_path.stem}_*.toml"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not backups:
                raise TensorZeroConfigError("No backups found for rollback")
            backup_path = backups[0]

        if not backup_path.exists():
            raise TensorZeroConfigError(f"Backup file not found: {backup_path}")

        try:
            # Create backup of current state before rollback
            self._create_backup()

            # Copy backup to config location
            shutil.copy2(backup_path, self.config_path)
            logger.info(f"Rolled back configuration to {backup_path}")

            # Reload configuration
            self.load()
        except Exception as e:
            error_msg = f"Failed to rollback to {backup_path}: {e}"
            logger.error(error_msg)
            raise TensorZeroConfigError(error_msg) from e

    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List all available configuration backups with metadata.

        Returns:
            List of dictionaries containing backup metadata (filename, size, mtime).
        """
        backups = []
        for backup_path in self.backup_dir.glob(f"{self.config_path.stem}_*.toml"):
            stat = backup_path.stat()
            backups.append({
                "filename": backup_path.name,
                "path": str(backup_path),
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

        return sorted(backups, key=lambda b: b["mtime"], reverse=True)

    def update_model(self, model_name: str, updates: Dict[str, Any]) -> "TensorZeroConfig":
        """
        Update a model configuration with the provided changes.

        Args:
            model_name: Name of the model to update.
            updates: Dictionary of configuration updates to apply.

        Returns:
            Self for method chaining.

        Raises:
            TensorZeroConfigError: If model not found or validation fails.
        """
        if "models" not in self.config:
            self.config["models"] = {}

        if model_name not in self.config["models"]:
            self.config["models"][model_name] = {}

        # Deep merge updates
        self._deep_update(self.config["models"][model_name], updates)

        # Validate updated model
        validate_model_config(model_name, self.config["models"][model_name])

        logger.info(f"Updated model configuration: {model_name}")
        return self

    def update_function(self, function_name: str, updates: Dict[str, Any]) -> "TensorZeroConfig":
        """
        Update a function configuration with the provided changes.

        Args:
            function_name: Name of the function to update.
            updates: Dictionary of configuration updates to apply.

        Returns:
            Self for method chaining.

        Raises:
            TensorZeroConfigError: If validation fails.
        """
        if "functions" not in self.config:
            self.config["functions"] = {}

        if function_name not in self.config["functions"]:
            self.config["functions"][function_name] = {}

        # Deep merge updates
        self._deep_update(self.config["functions"][function_name], updates)

        # Validate updated function
        validate_function_config(function_name, self.config["functions"][function_name])

        logger.info(f"Updated function configuration: {function_name}")
        return self

    def update_variant(
        self,
        function_name: str,
        variant_name: str,
        updates: Dict[str, Any],
    ) -> "TensorZeroConfig":
        """
        Update a variant configuration within a function.

        Args:
            function_name: Name of the parent function.
            variant_name: Name of the variant to update.
            updates: Dictionary of configuration updates to apply.

        Returns:
            Self for method chaining.

        Raises:
            TensorZeroConfigError: If function or variant not found, or validation fails.
        """
        if "functions" not in self.config or function_name not in self.config["functions"]:
            raise TensorZeroConfigError(f"Function not found: {function_name}")

        function_config = self.config["functions"][function_name]

        if "variants" not in function_config:
            function_config["variants"] = []

        # Find existing variant
        variant_found = False
        for variant in function_config["variants"]:
            if variant.get("name") == variant_name:
                self._deep_update(variant, updates)
                variant_found = True
                break

        # Create new variant if not found
        if not variant_found:
            new_variant = {"name": variant_name}
            self._deep_update(new_variant, updates)
            function_config["variants"].append(new_variant)

        # Validate updated variant
        validate_variant_config(variant_name, variant, function_config)

        logger.info(f"Updated variant '{variant_name}' in function '{function_name}'")
        return self

    def _deep_update(self, base: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """
        Recursively update a dictionary with new values.

        Args:
            base: Base dictionary to update (modified in-place).
            updates: Dictionary of updates to apply.
        """
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def get_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific model.

        Args:
            model_name: Name of the model.

        Returns:
            Model configuration dictionary or None if not found.
        """
        return self.config.get("models", {}).get(model_name)

    def get_function(self, function_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific function.

        Args:
            function_name: Name of the function.

        Returns:
            Function configuration dictionary or None if not found.
        """
        return self.config.get("functions", {}).get(function_name)

    def get_variant(
        self,
        function_name: str,
        variant_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific variant within a function.

        Args:
            function_name: Name of the parent function.
            variant_name: Name of the variant.

        Returns:
            Variant configuration dictionary or None if not found.
        """
        function_config = self.get_function(function_name)
        if not function_config:
            return None

        for variant in function_config.get("variants", []):
            if variant.get("name") == variant_name:
                return variant

        return None

    def to_dict(self) -> Dict[str, Any]:
        """
        Get the current configuration as a dictionary.

        Returns:
            Deep copy of the configuration dictionary.
        """
        return copy.deepcopy(self.config)

    def __repr__(self) -> str:
        """String representation of the configuration manager."""
        return f"TensorZeroConfig(path={self.config_path}, models={len(self.config.get('models', {}))}, functions={len(self.config.get('functions', {}))})"
