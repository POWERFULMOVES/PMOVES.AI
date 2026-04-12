"""Shared utilities for the secrets pipeline.

Single source-of-truth for placeholder detection, config path resolution,
and env-file parsing — used by brand_defaults, secrets_local_hydrate,
runtime_secrets_hydrate, auth_bootstrap_check, and local_cert_runners.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Placeholder Detection
# ---------------------------------------------------------------------------

PLACEHOLDER_VALUES: frozenset[str] = frozenset({
    "",
    "changeme",
    "change_me",
    "base64:change_me",
    "generate_from_wger_ui",
    "surreal_user_here",
    "surreal_pass_here",
    "root",
    "pmoves4482",
    "minioadmin",
    "none",
    "null",
    "your_key_here",
    "placeholder",
    "example",
    "master_key",
    "localhack",
    "example.com",
})


def normalize_env_value(value: str) -> str:
    """Strip whitespace and unquote matching outer single/double quotes."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def is_placeholder(value: str | None) -> bool:
    """Return True if value is missing, empty, or a known placeholder.

    Consolidated from four implementations:
    - brand_defaults._is_blank_or_placeholder
    - secrets_local_hydrate._is_empty_or_placeholder
    - runtime_secrets_hydrate._looks_placeholder
    - auth_bootstrap_check._looks_placeholder
    """
    if value is None:
        return True
    normalized = normalize_env_value(value)
    lowered = normalized.lower()
    if not lowered or lowered in PLACEHOLDER_VALUES:
        return True
    # Pattern: your_* prefix (any position), placeholder_* prefix
    if "your_" in lowered:
        return True
    if lowered.startswith("placeholder_"):
        return True
    # Example domain checks (URLs and emails)
    if lowered.endswith("@example.com") or lowered.endswith(".example.com"):
        return True
    try:
        candidate = normalized if "://" in normalized else f"https://{normalized}"
        host = (urllib.parse.urlparse(candidate).hostname or "").lower()
        if host in {"example.com", "www.example.com"}:
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Config Path Resolution
# ---------------------------------------------------------------------------

def host_config_dir() -> Path:
    """Return the platform-appropriate PMOVES config directory.

    Mirrors _config_paths.sh:pmoves_host_config_dir() logic exactly:
    checks APPDATA first (covers Windows + WSL with APPDATA set),
    then XDG_CONFIG_HOME, then platform-specific fallback.
    """
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / "pmoves"
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        return Path(xdg) / "pmoves"
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Roaming" / "pmoves"
    return Path.home() / ".config" / "pmoves"


def local_env_path() -> Path:
    """Resolve the local.env path, preferring project-local over per-user.

    Search order:
      1. pmoves/secrets/local.env (project-local, written by CI runner)
      2. $host_config_dir/secrets/local.env (per-user)
    """
    project_path = PROJECT_ROOT / "secrets" / "local.env"
    if project_path.exists():
        return project_path
    return host_config_dir() / "secrets" / "local.env"


# ---------------------------------------------------------------------------
# Env File Parsing
# ---------------------------------------------------------------------------

def parse_env_file(path: Path) -> Dict[str, str]:
    """Parse KEY=VALUE lines from a dotenv file, skipping comments and blanks."""
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:]
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value
    return values
