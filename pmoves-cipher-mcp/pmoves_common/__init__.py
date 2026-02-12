"""
PMOVES.AI Common Types Module for pmoves-cipher-mcp

Shared type definitions for the Cipher MCP bridge.
"""

from enum import Enum


class ServiceTier(str, Enum):
    """PMOVES service tiers (6-tier architecture)."""
    DATA = "data"
    API = "api"
    LLM = "llm"
    WORKER = "worker"
    MEDIA = "media"
    AGENT = "agent"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string value is a valid tier."""
        return value in (t.value for t in cls)


class HealthStatus(str, Enum):
    """Health status constants."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class MemoryCategory(str, Enum):
    """Memory storage categories for Cipher."""
    CODE_PATTERN = "code_pattern"
    DECISION = "decision"
    CONTEXT = "context"
    SUBMODULE = "submodule"
    ARCHITECTURE = "architecture"
    REASONING = "reasoning"


__all__ = [
    "ServiceTier",
    "HealthStatus",
    "MemoryCategory",
]
