"""Configuration for GitHub Branch Cleanup Service.

Provides centralized configuration management with environment variable overrides.
All settings have safe defaults for production use.
"""

import os
from typing import List


class Config:
    """Configuration settings for branch cleanup service."""

    # NATS Configuration
    NATS_URL: str = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")

    # Service Configuration
    SERVICE_PORT: int = int(os.getenv("SERVICE_PORT", "8100"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Branch Cleanup Settings
    BRANCH_STALE_DAYS: int = int(os.getenv("BRANCH_STALE_DAYS", "30"))
    DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")

    # Protected Branch Patterns (never delete these)
    PROTECTED_BRANCHES: List[str] = os.getenv(
        "PROTECTED_BRANCHES",
        "main,PMOVES.AI-Edition-Hardened,release-*"
    ).split(",")

    # GitHub Configuration
    GITHUB_ORG: str = os.getenv("GITHUB_ORG", "POWERFULMOVES")
    GITHUB_APP_ID: str = os.getenv("GH_APP_ID", "")
    GITHUB_APP_INSTALLATION_ID: str = os.getenv("GH_APP_INSTALLATION_ID", "")

    # Agent Zero MCP Configuration
    AGENTZERO_MCP_URL: str = os.getenv("AGENTZERO_MCP_URL", "http://agent-zero:8080/mcp")

    # Prometheus Metrics
    METRICS_PORT: int = int(os.getenv("METRICS_PORT", "9096"))

    @classmethod
    def is_protected_branch(cls, branch_name: str) -> bool:
        """Check if branch is protected.

        Args:
            branch_name: Name of the branch to check

        Returns:
            True if branch matches protected pattern
        """
        for pattern in cls.PROTECTED_BRANCHES:
            if pattern.endswith("*"):
                # Wildcard pattern (e.g., release-*)
                prefix = pattern[:-1]
                if branch_name.startswith(prefix):
                    return True
            else:
                # Exact match
                if branch_name == pattern:
                    return True
        return False

    @classmethod
    def validate(cls) -> None:
        """Validate configuration settings.

        Raises:
            ValueError: If required settings are missing or invalid
        """
        if not cls.GITHUB_APP_ID:
            raise ValueError("GH_APP_ID environment variable is required")
        if not cls.GITHUB_APP_INSTALLATION_ID:
            raise ValueError("GH_APP_INSTALLATION_ID environment variable is required")
        if cls.BRANCH_STALE_DAYS < 1:
            raise ValueError("BRANCH_STALE_DAYS must be at least 1")


# Global config instance
config = Config()
