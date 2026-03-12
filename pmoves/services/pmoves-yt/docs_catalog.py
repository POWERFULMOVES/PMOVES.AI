"""Compatibility shim for the authoritative PMOVES.YT docs catalog helpers."""

from __future__ import annotations

import pathlib
import sys

_SUBMODULE_ROOT = pathlib.Path(__file__).resolve().parents[3] / "PMOVES.YT"
if str(_SUBMODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SUBMODULE_ROOT))

from pmoves_yt_service.docs_catalog import *  # type: ignore  # noqa: F401,F403
