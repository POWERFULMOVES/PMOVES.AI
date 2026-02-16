"""
PMOVES.AI Service Registry for pmoves-cipher-mcp

Resolve Cipher Memory service URL.
"""

import os
from typing import Optional


def get_cipher_url() -> str:
    """
    Get Cipher Memory service URL.

    Resolution order:
    1. CIPHER_URL environment variable
    2. CIPHER_MEMORY_URL environment variable
    3. Default: http://localhost:8096 (remapped from Cipher's native 3000 to avoid Grafana conflict)

    Returns:
        Cipher Memory service URL
    """
    return (
        os.getenv("CIPHER_URL") or
        os.getenv("CIPHER_MEMORY_URL") or
        "http://localhost:8096"
    )


def get_nats_url() -> str:
    """Get NATS server URL (with credentials per PMOVES convention)."""
    return os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")


def get_tensorzero_url() -> str:
    """Get TensorZero gateway URL."""
    return (
        os.getenv("TENSORZERO_URL") or
        os.getenv("TENSORZERO_GATEWAY_URL") or
        "http://tensorzero-gateway:3030"
    )


__all__ = ["get_cipher_url", "get_nats_url", "get_tensorzero_url"]
