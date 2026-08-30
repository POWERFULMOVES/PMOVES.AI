"""Shared TensorZero configuration helpers for PMOVES services.

Consolidates the duplicated ``_tensorzero_openai_base()`` and
``_sync_openai_compat_env()`` previously found in agent-zero and archon.

Usage::

    from services.common.tensorzero import (
        tensorzero_openai_base,
        sync_openai_compat_env,
    )

    sync_openai_compat_env()  # one-shot setup at import time

The module also exposes :func:`check_tensorzero_connectivity` for services
that need to verify TensorZero reachability (hybrid standalone mode).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Sequence

logger = logging.getLogger(__name__)


def tensorzero_openai_base(
    *,
    check_connectivity: bool = False,
) -> str:
    """Return the OpenAI-compatible base URL derived from TensorZero settings.

    Resolution priority:
      1. ``TENSORZERO_BASE_URL`` (explicit, backward compatible)
      2. ``TENSORZERO_URL`` (parent PMOVES.AI TensorZero)
      3. ``host.docker.internal:3030`` (hybrid mode default, only when
         ``DOCKED_MODE != true``)

    If *check_connectivity* is ``True``, the function verifies that the
    resolved URL is actually reachable and returns an empty string when
    it is not.  This mirrors the hybrid-mode safety check that archon
    performs.

    Args:
        check_connectivity: When *True*, verify connectivity to the
            resolved TensorZero endpoint before returning.

    Returns:
        OpenAI-compatible base URL or empty string if not configured.
    """
    # First, check explicit TENSORZERO_BASE_URL (backward compatibility)
    base = (os.environ.get("TENSORZERO_BASE_URL") or "").strip()
    if not base:
        # Check for parent PMOVES.AI TensorZero in hybrid standalone mode
        parent_tensorzero = os.environ.get("TENSORZERO_URL")
        if parent_tensorzero:
            base = parent_tensorzero
        else:
            # Fallback to host.docker.internal for hybrid mode
            docked_mode = os.environ.get("DOCKED_MODE", "false").lower() == "true"
            if not docked_mode:
                base = "http://host.docker.internal:3030"

    if not base:
        return ""

    base = base.rstrip("/")
    if base.endswith("/openai/v1"):
        result = base
    elif base.endswith("/openai"):
        result = f"{base.rstrip('/')}/v1"
    else:
        result = f"{base}/openai/v1"

    if check_connectivity and "host.docker.internal" in result:
        if not _check_tensorzero_sync(result):
            logger.warning(
                "TensorZero unreachable at %s (hybrid mode). "
                "Ensure PMOVES.AI is running or set TENSORZERO_URL explicitly.",
                result,
            )
            return ""

    return result


# -----------------------------------------------------------------------
# OpenAI-compatible environment synchronisation
# -----------------------------------------------------------------------

_COMPAT_TARGET_ENVARS: Sequence[str] = (
    "OPENAI_COMPATIBLE_BASE_URL",
    "OPENAI_API_BASE",
    "OPENAI_COMPATIBLE_BASE_URL_LLM",
    "OPENAI_COMPATIBLE_BASE_URL_EMBEDDING",
    "OPENAI_COMPATIBLE_BASE_URL_TTS",
    "OPENAI_COMPATIBLE_BASE_URL_STT",
)


def sync_openai_compat_env(
    *,
    get_secret=None,
    check_connectivity: bool = False,
) -> None:
    """Sync TensorZero settings to OpenAI-compatible environment variables.

    Populates ``OPENAI_COMPATIBLE_BASE_URL``, ``OPENAI_API_BASE``, and
    related lane-specific variables (LLM, embedding, TTS, STT) from the
    best available source.

    Also derives ``OPENAI_API_KEY`` from ``TENSORZERO_API_KEY`` when the
    former is not set.

    Args:
        get_secret: Secret-fetcher callable ``(key: str) -> str | None``.
            When *None*, falls back to :func:`services.common.env.get_secret`.
        check_connectivity: Forward to :func:`tensorzero_openai_base` to
            verify TensorZero reachability before setting env vars.
    """
    # Late import to avoid circular / hard dependency
    if get_secret is None:
        from services.common.env import get_secret as _get_secret
        get_secret = _get_secret

    resolved_base = ""
    for candidate in (
        os.environ.get("OPENAI_COMPATIBLE_BASE_URL"),
        os.environ.get("OPENAI_API_BASE"),
        tensorzero_openai_base(check_connectivity=check_connectivity),
    ):
        value = (candidate or "").strip()
        if value:
            resolved_base = value
            break

    if resolved_base:
        updated: list[str] = []
        for target in _COMPAT_TARGET_ENVARS:
            current = (os.environ.get(target) or "").strip()
            if current:
                continue
            os.environ[target] = resolved_base
            os.putenv(target, resolved_base)
            updated.append(target)
        if updated:
            logger.info("OpenAI-compatible base resolved to %s", resolved_base)
        else:
            logger.debug("OpenAI-compatible base already set to %s", resolved_base)

    key = (get_secret("OPENAI_API_KEY") or "").strip()
    if not key:
        tz_key = (get_secret("TENSORZERO_API_KEY") or "").strip()
        if tz_key:
            os.environ["OPENAI_API_KEY"] = tz_key
            os.putenv("OPENAI_API_KEY", tz_key)
            logger.info("OpenAI-compatible API key derived from TensorZero settings")


# -----------------------------------------------------------------------
# Connectivity helpers
# -----------------------------------------------------------------------


async def check_tensorzero_connectivity(base_url: str) -> bool:
    """Check if TensorZero is reachable at the given URL."""
    try:
        import httpx

        test_url = base_url.replace("/openai/v1", "").replace("/openai", "")
        test_url = f"{test_url.rstrip('/')}/models"

        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(test_url)
            return response.status_code == 200
    except Exception:
        return False


def _check_tensorzero_sync(base_url: str) -> bool:
    """Synchronous wrapper for :func:`check_tensorzero_connectivity`."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(check_tensorzero_connectivity(base_url))
        finally:
            loop.close()
    except Exception:
        return False


# Backward-compatible aliases matching original private names in services.
_tensorzero_openai_base = tensorzero_openai_base
_sync_openai_compat_env = sync_openai_compat_env

__all__ = [
    "tensorzero_openai_base",
    "sync_openai_compat_env",
    "check_tensorzero_connectivity",
    "_tensorzero_openai_base",
    "_sync_openai_compat_env",
]
