"""
Schema Validator for Event Data

Provides JSON schema validation for event payloads.
Ensures event data conforms to expected structures.

Usage:
    from pmoves.services.agent_zero.python.events.schema import SchemaValidator

    validator = SchemaValidator({
        "type": "object",
        "properties": {
            "agent_id": {"type": "string"},
            "capabilities": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["agent_id"]
    })

    validator.validate({"agent_id": "agent-zero", "capabilities": ["code_generation"]})
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("pmoves.agent_zero.events.schema")


class SchemaValidator:
    """
    JSON schema validator for event data.

    Uses jsonschema library if available, otherwise performs basic validation.
    """

    def __init__(self, schema: Dict[str, Any]):
        """
        Initialize validator with JSON schema.

        Args:
            schema: JSON schema dictionary
        """
        self.schema = schema
        self._validator = None

        # Try to import jsonschema for full validation
        try:
            from jsonschema import validate, ValidationError
            from jsonschema.validators import validator_for

            self._validate_fn = validate
            self._ValidationError = ValidationError
            self._available = True

            # Pre-compile schema for performance
            cls = validator_for(schema)
            self._validator = cls(schema)

        except ImportError:
            logger.warning(
                "jsonschema library not available, using basic validation. "
                "Install with: pip install jsonschema"
            )
            self._available = False

    def validate(self, data: Dict[str, Any]) -> bool:
        """
        Validate data against schema.

        Args:
            data: Event payload to validate

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails
        """
        if self._available and self._validator:
            try:
                self._validator.validate(data)
                return True
            except self._ValidationError as e:
                raise ValueError(f"Schema validation failed: {e.message}")
        else:
            # Basic validation (check required fields)
            return self._basic_validate(data)

    def _basic_validate(self, data: Dict[str, Any]) -> bool:
        """
        Basic validation without jsonschema library.

        Checks required fields and basic types.
        """
        required = self.schema.get("required", [])
        properties = self.schema.get("properties", {})

        # Check required fields
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        # Check types if specified
        for field, value in data.items():
            if field in properties:
                field_schema = properties[field]
                expected_type = field_schema.get("type")

                if expected_type == "string" and not isinstance(value, str):
                    raise ValueError(f"Field '{field}' must be string")
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    raise ValueError(f"Field '{field}' must be number")
                elif expected_type == "integer" and not isinstance(value, int):
                    raise ValueError(f"Field '{field}' must be integer")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    raise ValueError(f"Field '{field}' must be boolean")
                elif expected_type == "array" and not isinstance(value, list):
                    raise ValueError(f"Field '{field}' must be array")
                elif expected_type == "object" and not isinstance(value, dict):
                    raise ValueError(f"Field '{field}' must be object")

        return True


# =============================================================================
# Predefined Schemas for Common Event Types
# =============================================================================

AGENT_STARTED_SCHEMA = {
    "type": "object",
    "properties": {
        "agent_id": {"type": "string"},
        "agent_type": {"type": "string"},
        "capabilities": {"type": "array", "items": {"type": "string"}},
        "version": {"type": "string"},
    },
    "required": ["agent_id"],
}

AGENT_ERROR_SCHEMA = {
    "type": "object",
    "properties": {
        "agent_id": {"type": "string"},
        "error_type": {"type": "string"},
        "error_message": {"type": "string"},
        "stack_trace": {"type": "string"},
        "context": {"type": "object"},
    },
    "required": ["agent_id", "error_type", "error_message"],
}

TASK_CREATED_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {"type": "string"},
        "task_type": {"type": "string"},
        "instruction": {"type": "string"},
        "priority": {"type": "integer"},
        "assigned_to": {"type": "string"},
        "context": {"type": "object"},
    },
    "required": ["task_id", "task_type", "instruction"],
}

TASK_COMPLETED_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {"type": "string"},
        "result": {"type": "object"},
        "duration_ms": {"type": "integer"},
        "artifacts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["task_id"],
}

TASK_FAILED_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {"type": "string"},
        "error_type": {"type": "string"},
        "error_message": {"type": "string"},
        "retry_count": {"type": "integer"},
    },
    "required": ["task_id", "error_type"],
}

TOOL_STARTED_SCHEMA = {
    "type": "object",
    "properties": {
        "tool_name": {"type": "string"},
        "tool_version": {"type": "string"},
        "parameters": {"type": "object"},
        "agent_id": {"type": "string"},
    },
    "required": ["tool_name"],
}

TOOL_COMPLETED_SCHEMA = {
    "type": "object",
    "properties": {
        "tool_name": {"type": "string"},
        "result": {"type": "object"},
        "duration_ms": {"type": "integer"},
        "agent_id": {"type": "string"},
    },
    "required": ["tool_name"],
}

TOOL_FAILED_SCHEMA = {
    "type": "object",
    "properties": {
        "tool_name": {"type": "string"},
        "error_type": {"type": "string"},
        "error_message": {"type": "string"},
        "agent_id": {"type": "string"},
    },
    "required": ["tool_name", "error_type"],
}

A2A_TASK_SUBMITTED_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {"type": "string"},
        "from_agent": {"type": "string"},
        "to_agent": {"type": "string"},
        "instruction": {"type": "string"},
        "a2a_version": {"type": "string"},
    },
    "required": ["task_id", "from_agent", "to_agent", "instruction"],
}

A2A_ARTIFACT_READY_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {"type": "string"},
        "agent_id": {"type": "string"},
        "artifact_type": {"type": "string"},
        "artifact_uri": {"type": "string"},
        "metadata": {"type": "object"},
    },
    "required": ["task_id", "agent_id", "artifact_type"],
}


# =============================================================================
# Schema Registry
# =============================================================================

SCHEMA_REGISTRY: Dict[str, Dict[str, Any]] = {
    "AGENT_STARTED": AGENT_STARTED_SCHEMA,
    "AGENT_ERROR": AGENT_ERROR_SCHEMA,
    "TASK_CREATED": TASK_CREATED_SCHEMA,
    "TASK_COMPLETED": TASK_COMPLETED_SCHEMA,
    "TASK_FAILED": TASK_FAILED_SCHEMA,
    "TOOL_STARTED": TOOL_STARTED_SCHEMA,
    "TOOL_COMPLETED": TOOL_COMPLETED_SCHEMA,
    "TOOL_FAILED": TOOL_FAILED_SCHEMA,
    "A2A_TASK_SUBMITTED": A2A_TASK_SUBMITTED_SCHEMA,
    "A2A_ARTIFACT_READY": A2A_ARTIFACT_READY_SCHEMA,
}


def get_schema(event_type: str) -> Optional[Dict[str, Any]]:
    """
    Get schema for event type from registry.

    Args:
        event_type: Event type name (e.g., "AGENT_STARTED")

    Returns:
        Schema dictionary or None if not found
    """
    return SCHEMA_REGISTRY.get(event_type)


def register_schema(event_type: str, schema: Dict[str, Any]) -> None:
    """
    Register custom schema for event type.

    Args:
        event_type: Event type name
        schema: JSON schema dictionary
    """
    SCHEMA_REGISTRY[event_type] = schema
    logger.info(f"Registered schema for {event_type}")


def load_schemas_from_directory(schema_dir: Path) -> None:
    """
    Load schemas from JSON files in directory.

    Args:
        schema_dir: Directory containing .json schema files

    File naming convention: {event_type}.schema.json
    """
    if not schema_dir.exists():
        logger.warning(f"Schema directory not found: {schema_dir}")
        return

    for schema_file in schema_dir.glob("*.schema.json"):
        try:
            event_type = schema_file.stem.replace(".schema", "")
            with open(schema_file) as f:
                schema = json.load(f)
            register_schema(event_type, schema)
            logger.info(f"Loaded schema for {event_type} from {schema_file}")
        except Exception as e:
            logger.error(f"Failed to load schema from {schema_file}: {e}")
