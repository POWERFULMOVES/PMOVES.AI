"""Helpers for fetching Qwen cookbook markdown resources."""

from __future__ import annotations

import logging
from typing import Callable, Dict, Iterable, Optional
from urllib import error as urlerror
from urllib import request as urlrequest

logger = logging.getLogger(__name__)

_RAW_BASE_URL = "https://raw.githubusercontent.com/QwenLM/Qwen3-VL/main/cookbooks/"
_CACHE: Dict[str, str] = {}


class CookbookFetchError(RuntimeError):
    """Raised when a cookbook cannot be retrieved from GitHub."""


def _normalise_path(path: str) -> str:
    cleaned = path.strip()
    if cleaned.startswith("https://") or cleaned.startswith("http://"):
        return cleaned
    return cleaned.lstrip("/")


def _fetch_markdown(path: str) -> str:
    url = path if path.startswith("http") else f"{_RAW_BASE_URL}{path}"
    try:
        with urlrequest.urlopen(url, timeout=15) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)
    except (urlerror.URLError, urlerror.HTTPError) as exc:  # pragma: no cover - network failure path
        raise CookbookFetchError(f"Failed to fetch cookbook '{path}': {exc}") from exc


def load_cookbooks(
    paths: Iterable[str],
    *,
    fetcher: Optional[Callable[[str], str]] = None,
) -> Dict[str, str]:
    """Fetch and cache the requested cookbook markdown files.

    Parameters
    ----------
    paths:
        The cookbook paths relative to the Qwen repository (e.g. "vision/README.md") or
        fully qualified HTTP(S) URLs.
    fetcher:
        Optional override used by tests to avoid hitting the network.

    Returns
    -------
    Dict[str, str]
        Mapping of normalised cookbook paths to the fetched markdown content.
    """

    fetch = fetcher or _fetch_markdown
    collected: Dict[str, str] = {}
    for raw in paths:
        normalised = _normalise_path(raw)
        if not normalised:
            continue
        if normalised not in _CACHE:
            logger.debug("Fetching cookbook resource: %s", normalised)
            _CACHE[normalised] = fetch(normalised)
        collected[normalised] = _CACHE[normalised]
    return collected


def clear_cache() -> None:
    """Clear the in-memory cookbook cache (useful for tests)."""

    _CACHE.clear()
