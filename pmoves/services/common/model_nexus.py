from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

try:
    import yaml
except ImportError:
    yaml = None

_PMOVES_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_NEXUS_PATH = _PMOVES_DIR / "config" / "model_nexus.yaml"


class NexusConfigError(RuntimeError):
    """Raised when the Nexus provider registry is missing or malformed."""


def model_nexus_path() -> Path:
    """Return the canonical Model Nexus config path."""

    return _DEFAULT_NEXUS_PATH


@lru_cache(maxsize=4)
def _load_model_nexus_cached(resolved_path: str) -> dict[str, Any]:
    path = Path(resolved_path)
    if not path.exists():
        raise NexusConfigError(f"Model Nexus config not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or "providers" not in data or "lanes" not in data:
        raise NexusConfigError(f"Model Nexus config is malformed: {path}")
    return data


def load_model_nexus(path: str | Path | None = None) -> dict[str, Any]:
    """Load the Model Nexus registry from disk.

    The config is cached by absolute path because most services read the shared
    registry repeatedly during startup and health checks.
    """

    target = Path(path) if path is not None else model_nexus_path()
    return _load_model_nexus_cached(str(target.resolve()))


def get_nexus_provider(name: str, config: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    """Return a provider definition from the Nexus registry."""

    data = config or load_model_nexus()
    providers = data.get("providers", {})
    if name not in providers:
        raise KeyError(f"Unknown Nexus provider: {name}")
    return providers[name]


def get_nexus_lane(name: str, config: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    """Return a lane definition from the Nexus registry."""

    data = config or load_model_nexus()
    lanes = data.get("lanes", {})
    if name not in lanes:
        raise KeyError(f"Unknown Nexus lane: {name}")
    return lanes[name]


def provider_allowed_for_lane(
    lane_name: str,
    provider_name: str,
    config: Mapping[str, Any] | None = None,
) -> bool:
    """Return True when a provider is valid for the given lane.

    The lane default is always allowed. Native overrides must be explicitly
    listed in `allowed_native_overrides`.
    """

    lane = get_nexus_lane(lane_name, config=config)
    if provider_name == lane.get("default_provider"):
        return True
    return provider_name in set(lane.get("allowed_native_overrides", []))


def provider_requires_nexus_adapter(
    provider_name: str,
    config: Mapping[str, Any] | None = None,
) -> bool:
    """Return True when the provider is a native SDK lane that must preserve parity."""

    provider = get_nexus_provider(provider_name, config=config)
    return provider.get("role") == "native_provider"
