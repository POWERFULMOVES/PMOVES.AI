#!/usr/bin/env python3
"""PMOVES Environment Validator for Tier Layout.

Validates the 6-tier environment architecture:
- Tier 1 (data): Database credentials (PostgreSQL, Neo4j, Meilisearch, MinIO)
- Tier 2 (api): Internal service URLs and connections
- Tier 3 (llm): External LLM provider API keys
- Tier 4 (media): Media processing (YouTube, Whisper, YOLO, Jellyfin)
- Tier 5 (agent): Agent orchestration (NATS, Supabase, Hi-RAG)
- Tier 6 (worker): Data processing workers
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Tier definitions with required variables and validation rules
TIER_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "data": {
        "file": "env.tier-data",
        "description": "Database credentials (PostgreSQL, Neo4j, Meilisearch, MinIO)",
        "required": [
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "POSTGRES_HOSTNAME",
            "POSTGRES_PORT",
            "NEO4J_AUTH",
            "MEILI_MASTER_KEY",
            "MINIO_ROOT_USER",
            "MINIO_ROOT_PASSWORD",
        ],
        "validators": {
            "POSTGRES_PASSWORD": lambda v: len(v) >= 16,
            "NEO4J_AUTH": lambda v: v.startswith("neo4j/"),
            "MEILI_MASTER_KEY": lambda v: len(v) >= 32,
        },
    },
    "api": {
        "file": "env.tier-api",
        "description": "Internal service URLs and connections",
        "required": [
            "SUPABASE_JWT_SECRET",
            "SUPABASE_SERVICE_ROLE_KEY",
            "PRESIGN_SHARED_SECRET",
        ],
        "validators": {
            "SUPABASE_JWT_SECRET": lambda v: len(v) >= 32,
            "PRESIGN_SHARED_SECRET": lambda v: len(v) >= 16,
        },
    },
    "llm": {
        "file": "env.tier-llm",
        "description": "External LLM provider API keys",
        "optional": [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "GROQ_API_KEY",
            "MISTRAL_API_KEY",
            "COHERE_API_KEY",
            "DEEPSEEK_API_KEY",
            "TOGETHER_AI_API_KEY",
            "OPENROUTER_API_KEY",
            "PERPLEXITYAI_API_KEY",
            "XAI_API_KEY",
            "VOYAGE_API_KEY",
            "ELEVENLABS_API_KEY",
            "FIREWORKS_AI_API_KEY",
            "OLLAMA_BASE_URL",
            "TENSORZERO_API_KEY",
        ],
        "validators": {
            # At least one LLM provider should be configured
            "_any": lambda vars: any(k.startswith(("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")) and v for k, v in vars.items()),
        },
    },
    "media": {
        "file": "env.tier-media",
        "description": "Media processing (YouTube, Whisper, YOLO, Jellyfin, Invidious)",
        "optional": [
            "JELLYFIN_API_KEY",
            "JELLYFIN_USER_ID",
            "JELLYFIN_URL",
            "JELLYFIN_PUBLISHED_URL",
            "INVIDIOUS_HMAC_KEY",
            "INVIDIOUS_COMPANION_KEY",
            "DISCORD_WEBHOOK_URL",
            "DISCORD_USERNAME",
            "DISCORD_AVATAR_URL",
        ],
        "validators": {
            "JELLYFIN_URL": lambda v: v.startswith(("http://", "https://")),
            "INVIDIOUS_HMAC_KEY": lambda v: len(v) >= 32,
        },
    },
    "agent": {
        "file": "env.tier-agent",
        "description": "Agent orchestration (NATS, Supabase, Hi-RAG, Agent Zero)",
        "required": [
            "NATS_URL",
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
        ],
        "optional": [
            "OPEN_NOTEBOOK_API_TOKEN",
            "OPEN_NOTEBOOK_API_URL",
            "OPEN_NOTEBOOK_PASSWORD",
            "TENSORZERO_URL",
            "HI_RAG_URL",
            "AGENT_ZERO_URL",
            "DISCORD_WEBHOOK_URL",
            "TELEGRAM_BOT_TOKEN",
            "TAILSCALE_AUTHKEY",
        ],
        "validators": {
            "NATS_URL": lambda v: v.startswith(("http://", "https://", "nats://")),
            "SUPABASE_URL": lambda v: v.startswith(("http://", "https://")),
        },
    },
    "worker": {
        "file": "env.tier-worker",
        "description": "Data processing workers (TensorZero, Qdrant, Meilisearch)",
        "optional": [
            "QDRANT_URL",
            "MEILI_ADDR",
            "TENSORZERO_URL",
            "SENTENCE_MODEL",
        ],
        "validators": {
            "QDRANT_URL": lambda v: v.startswith(("http://", "https://")),
            "MEILI_ADDR": lambda v: v.startswith(("http://", "https://")),
        },
    },
}

# Patterns that indicate placeholder/bogus values
PLACEHOLDER_PATTERNS = [
    re.compile(r"^changeme", re.IGNORECASE),
    re.compile(r"^your_.*_here", re.IGNORECASE),
    re.compile(r"^placeholder", re.IGNORECASE),
    re.compile(r"^xxx+$", re.IGNORECASE),
    re.compile(r"^TODO", re.IGNORECASE),
    re.compile(r"^<.*>$"),
]


class ValidationError:
    """Represents a single validation error."""

    def __init__(self, tier: str, variable: str, message: str, severity: str = "error"):
        self.tier = tier
        self.variable = variable
        self.message = message
        self.severity = severity  # "error", "warning", "info"

    def __str__(self) -> str:
        severity_symbol = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}[self.severity]
        return f"{severity_symbol} [{self.tier}] {self.variable}: {self.message}"

    def to_dict(self) -> Dict[str, str]:
        return {
            "tier": self.tier,
            "variable": self.variable,
            "message": self.message,
            "severity": self.severity,
        }


class ValidationReport:
    """Validation report for a tier or all tiers."""

    def __init__(self, tier: Optional[str] = None):
        self.tier = tier  # None means all tiers
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.info: List[ValidationError] = []

    def add_error(self, error: ValidationError) -> None:
        if error.severity == "error":
            self.errors.append(error)
        elif error.severity == "warning":
            self.warnings.append(error)
        else:
            self.info.append(error)

    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def summary(self) -> str:
        lines = []
        if self.tier:
            lines.append(f"=== Tier {self.tier.upper()} Validation ===\n")
        else:
            lines.append("=== Environment Validation Report ===\n")

        # Print errors
        if self.errors:
            lines.append("Errors:")
            for error in self.errors:
                lines.append(f"  {error}")
            lines.append("")

        # Print warnings
        if self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  {warning}")
            lines.append("")

        # Print info
        if self.info:
            lines.append("Info:")
            for info in self.info:
                lines.append(f"  {info}")
            lines.append("")

        # Summary
        lines.append(
            f"Summary: {len(self.errors)} error(s), {len(self.warnings)} warning(s), {len(self.info)} info"
        )

        if self.is_valid():
            lines.append("✅ Validation passed!")

        return "\n".join(lines)


def is_placeholder_value(value: str) -> bool:
    """Check if a value appears to be a placeholder."""
    if not value:
        return True
    for pattern in PLACEHOLDER_PATTERNS:
        if pattern.search(value):
            return True
    return False


def is_valid_url(value: str) -> bool:
    """Basic URL validation."""
    return value.startswith(("http://", "https://", "nats://"))


def validate_variable(tier: str, variable: str, value: str) -> Optional[ValidationError]:
    """Validate a single variable value."""
    if not value:
        return ValidationError(tier, variable, "Variable is not set", "error")

    # Check for placeholder values
    if is_placeholder_value(value):
        return ValidationError(
            tier, variable, f"Value appears to be a placeholder: '{value}'", "error"
        )

    # Run tier-specific validators
    tier_def = TIER_DEFINITIONS.get(tier, {})
    validators = tier_def.get("validators", {})
    if variable in validators:
        validator = validators[variable]
        try:
            if not validator(value):
                return ValidationError(
                    tier, variable, f"Value failed validation for {variable}", "error"
                )
        except Exception as e:
            return ValidationError(
                tier, variable, f"Validation error: {e}", "error"
            )

    return None


def validate_tier(tier: str, base_dir: Optional[Path] = None) -> ValidationReport:
    """Validate a single tier env file."""
    if tier not in TIER_DEFINITIONS:
        report = ValidationReport(tier)
        report.add_error(ValidationError(tier, "N/A", f"Unknown tier: {tier}", "error"))
        return report

    if base_dir is None:
        base_dir = Path.cwd()

    tier_def = TIER_DEFINITIONS[tier]
    tier_file = base_dir / "pmoves" / tier_def["file"]

    report = ValidationReport(tier)

    # Check file exists
    if not tier_file.exists():
        report.add_error(
            ValidationError(tier, tier_file.name, f"Tier file not found: {tier_file}", "error")
        )
        return report

    # Parse env file
    env_vars = {}
    try:
        with open(tier_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    except Exception as e:
        report.add_error(
            ValidationError(tier, tier_file.name, f"Failed to read file: {e}", "error")
        )
        return report

    # Check required variables
    required = tier_def.get("required", [])
    for var in required:
        if var not in env_vars:
            report.add_error(
                ValidationError(tier, var, f"Required variable not set", "error")
            )
        else:
            error = validate_variable(tier, var, env_vars[var])
            if error:
                report.add_error(error)

    # Check optional variables
    optional = tier_def.get("optional", [])
    for var in optional:
        if var in env_vars:
            error = validate_variable(tier, var, env_vars[var])
            if error:
                report.add_error(error)

    # Run _any validators (check if at least one of a set is configured)
    validators = tier_def.get("validators", {})
    for var_name, validator in validators.items():
        if var_name == "_any":
            try:
                if not validator(env_vars):
                    report.add_error(
                        ValidationError(
                            tier,
                            "any_provider",
                            "At least one provider from this tier should be configured",
                            "warning",
                        )
                    )
            except Exception:
                pass

    return report


def validate_all_tiers(base_dir: Optional[Path] = None) -> ValidationReport:
    """Validate all tier env files."""
    if base_dir is None:
        base_dir = Path.cwd()

    report = ValidationReport(None)

    for tier in TIER_DEFINITIONS.keys():
        tier_report = validate_tier(tier, base_dir)
        report.errors.extend(tier_report.errors)
        report.warnings.extend(tier_report.warnings)
        report.info.extend(tier_report.info)

    return report


def run_connectivity_checks(base_dir: Optional[Path] = None) -> List[ValidationError]:
    """Run service connectivity checks (if Docker is running)."""
    errors = []

    try:
        import subprocess

        # Check if Docker is running
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        docker_running = result.returncode == 0
    except Exception:
        docker_running = False

    if not docker_running:
        errors.append(
            ValidationError(
                "connectivity",
                "docker",
                "Docker is not running - skipping service connectivity checks",
                "info",
            )
        )
        return errors

    # Check common services
    services = {
        "postgres": ("postgres", 5432),
        "neo4j": ("neo4j", 7474),
        "qdrant": ("qdrant", 6333),
        "meilisearch": ("meilisearch", 7700),
        "minio": ("minio", 9000),
        "nats": ("nats", 4222),
    }

    for service_name, (container, port) in services.items():
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={container}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            running = bool(result.stdout.strip())
            if running:
                errors.append(
                    ValidationError(
                        "connectivity",
                        service_name,
                        f"Service is running (port {port})",
                        "info",
                    )
                )
            else:
                errors.append(
                    ValidationError(
                        "connectivity",
                        service_name,
                        f"Service is not running",
                        "warning",
                    )
                )
        except Exception as e:
            errors.append(
                ValidationError(
                    "connectivity",
                    service_name,
                    f"Could not check service: {e}",
                    "warning",
                )
            )

    return errors


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="PMOVES Environment Validator")
    parser.add_argument(
        "--tier",
        choices=list(TIER_DEFINITIONS.keys()) + ["all"],
        default="all",
        help="Tier to validate (default: all)",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Base directory for tier files (default: current directory)",
    )
    parser.add_argument(
        "--connectivity",
        action="store_true",
        help="Run service connectivity checks",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    # Validate
    if args.tier == "all":
        report = validate_all_tiers(args.base_dir)
    else:
        report = validate_tier(args.tier, args.base_dir)

    # Run connectivity checks if requested
    if args.connectivity:
        connectivity_errors = run_connectivity_checks(args.base_dir)
        for error in connectivity_errors:
            report.add_error(error)

    # Output
    if args.json:
        import json

        output = {
            "valid": report.is_valid(),
            "tier": report.tier,
            "errors": [e.to_dict() for e in report.errors],
            "warnings": [e.to_dict() for e in report.warnings],
            "info": [e.to_dict() for e in report.info],
        }
        print(json.dumps(output, indent=2))
    else:
        print(report.summary())

    return 0 if report.is_valid() else 1


if __name__ == "__main__":
    sys.exit(main())
