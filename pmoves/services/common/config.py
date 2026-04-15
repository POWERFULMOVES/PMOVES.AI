"""Base configuration for PMOVES services.

Provides a shared ``BaseServiceSettings`` that standardises environment
variable loading, secret resolution, and common configuration fields
across all PMOVES services.

Usage::

    from services.common.config import BaseServiceSettings

    class MyServiceSettings(BaseServiceSettings):
        my_option: str = "default"

    settings = MyServiceSettings()
"""

from __future__ import annotations

import os
from typing import Optional

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings  # type: ignore[no-redef]

from .env import get_secret


def env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean from an environment variable.

    Truthy values: ``1``, ``true``, ``yes``, ``on`` (case-insensitive).

    Args:
        name: Environment variable name.
        default: Value when the variable is unset.

    Returns:
        Parsed boolean.
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class BaseServiceSettings(BaseSettings):
    """Base settings class for PMOVES services.

    Provides common configuration fields that most services need:

    - ``nats_url``: NATS server URL
    - ``port``: HTTP listen port
    - ``log_level``: Logging verbosity
    - ``docked_mode``: Whether running in Docker
    - ``debug``: Debug mode flag

    Subclass this for service-specific settings::

        class MySettings(BaseServiceSettings):
            my_api_key: str = ""

            class Config:
                env_prefix = "MY_SERVICE_"
    """

    nats_url: str = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")
    port: int = int(os.getenv("PORT", "8080"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    docked_mode: bool = env_bool("DOCKED_MODE", default=False)
    debug: bool = env_bool("DEBUG", default=False)

    model_config = {"extra": "ignore"}

    def get_secret(self, key: str) -> Optional[str]:
        """Resolve a secret using the standard PMOVES secret helper."""
        return get_secret(key)


class TensorZeroSettings(BaseSettings):
    """Settings for TensorZero/OpenAI-compatible endpoints.

    Captures all TensorZero-related environment variables in one place.
    """

    tensorzero_base_url: str = os.getenv("TENSORZERO_BASE_URL", "")
    tensorzero_url: str = os.getenv("TENSORZERO_URL", "")
    tensorzero_api_key: str = ""
    openai_compatible_base_url: str = os.getenv("OPENAI_COMPATIBLE_BASE_URL", "")
    openai_api_base: str = os.getenv("OPENAI_API_BASE", "")
    openai_api_key: str = ""

    model_config = {"extra": "ignore"}

    def resolve_api_key(self) -> str:
        """Return the best available API key."""
        key = get_secret("OPENAI_API_KEY") or self.openai_api_key
        if not key:
            tz_key = get_secret("TENSORZERO_API_KEY") or self.tensorzero_api_key
            if tz_key:
                return tz_key
        return key or ""


__all__ = [
    "BaseServiceSettings",
    "TensorZeroSettings",
    "env_bool",
]
