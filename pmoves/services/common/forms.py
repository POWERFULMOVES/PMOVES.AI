"""Shared helpers for resolving agent form configuration.

This module centralizes the default form name and directory logic so
services like Agent Zero and Archon agree on the active persona without
relying on duplicated environment parsing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Mapping, Optional

DEFAULT_AGENT_FORM = "POWERFULMOVES"
DEFAULT_AGENT_FORMS_DIR = "configs/agents/forms"


def _first_present(env: Mapping[str, str], keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        value = env.get(key)
        if value:
            return value
    return None


def resolve_form_name(
    *,
    env: Optional[Mapping[str, str]] = None,
    prefer_keys: Iterable[str] = (),
    fallback: str = DEFAULT_AGENT_FORM,
) -> str:
    """Return the resolved form name given optional environment overrides."""

    env_map = os.environ if env is None else env
    preferred = _first_present(env_map, prefer_keys)
    if preferred:
        return preferred
    return env_map.get("AGENT_FORM", fallback) or fallback


def resolve_forms_dir(
    *,
    env: Optional[Mapping[str, str]] = None,
    prefer_keys: Iterable[str] = (),
    fallback: str = DEFAULT_AGENT_FORMS_DIR,
) -> str:
    """Return the resolved forms directory as a string path."""

    env_map = os.environ if env is None else env
    preferred = _first_present(env_map, prefer_keys)
    if preferred:
        return preferred
    return env_map.get("AGENT_FORMS_DIR", fallback) or fallback


def resolve_forms_dir_path(
    *,
    env: Optional[Mapping[str, str]] = None,
    prefer_keys: Iterable[str] = (),
    fallback: str = DEFAULT_AGENT_FORMS_DIR,
) -> Path:
    """Return the resolved forms directory as a :class:`Path`."""

    return Path(resolve_forms_dir(env=env, prefer_keys=prefer_keys, fallback=fallback))
