"""Compatibility shim for the authoritative PMOVES.YT submodule runtime."""

from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace



def _locate_submodule_root() -> pathlib.Path:
    """Find the PMOVES.YT submodule by walking up from this file.

    This was `parents[3]`, a hardcoded count valid only for the repo layout
    (pmoves/services/pmoves-yt/yt.py, three levels below the repo root). Any
    shallower layout raised IndexError *at import*, before the `_IMPL.exists()`
    fallback below could run. That is what made every container built from this
    directory unstartable: `COPY . .` into `WORKDIR /app` leaves the file at
    /app/yt.py, which has two parents, not four.

    Publishing no longer builds from this directory (the GHCR matrix builds the
    fork's own Dockerfile), but the crash class should not survive here either.
    """
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "PMOVES.YT"
        if candidate.is_dir():
            return candidate
    # Not found. Return a path that does not exist rather than raising, so the
    # `_IMPL.exists()` guard below decides what happens.
    return here.parent / "PMOVES.YT"


_SUBMODULE_ROOT = _locate_submodule_root()
if str(_SUBMODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SUBMODULE_ROOT))

_IMPL = _SUBMODULE_ROOT / "pmoves_yt_service" / "yt.py"

if _IMPL.exists():
    __package__ = "pmoves_yt_service"
    __path__ = [str(_SUBMODULE_ROOT / "pmoves_yt_service")]
    code = _IMPL.read_text(encoding="utf-8")
    exec(compile(code, str(_IMPL), "exec"))

if globals().get("yt_dlp") is None:
    yt_dlp = SimpleNamespace(YoutubeDL=None)
