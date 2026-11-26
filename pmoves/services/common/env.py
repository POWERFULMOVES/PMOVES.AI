"""Secret-aware environment helpers with Docker *_FILE support."""

import os
from pathlib import Path


def get_secret(key: str, default: str | None = None) -> str | None:
    """Read secret from env var, falling back to {KEY}_FILE path.

    Priority: {KEY} env var -> {KEY}_FILE file contents -> default.
    """
    value = os.environ.get(key)
    if value:
        return value
    file_path = os.environ.get(f"{key}_FILE")
    if file_path:
        p = Path(file_path)
        if p.is_file():
            return p.read_text().strip()
    return default


def require_secret(key: str) -> str:
    """Like get_secret but raises if missing."""
    value = get_secret(key)
    if not value:
        raise RuntimeError(f"{key} not set (checked env var and {key}_FILE)")
    return value


# Canonical service-role key first; SUPABASE_KEY is a read-fallback alias only
# (#3498: per-node keys no longer ship from GitHub Prod, and the node minter
# fills every alias with the same role key).
SUPABASE_SERVICE_KEY_ORDER = (
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_KEY",
)


def supabase_service_key(default: str | None = None) -> str | None:
    """Return the Supabase service-role key, canonical name first.

    Order: SUPABASE_SERVICE_ROLE_KEY -> SUPABASE_SERVICE_KEY -> SUPABASE_KEY
    (each via get_secret, so *_FILE works) -> default.
    """
    for name in SUPABASE_SERVICE_KEY_ORDER:
        value = get_secret(name)
        if value:
            return value
    return default
