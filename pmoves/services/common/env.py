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
