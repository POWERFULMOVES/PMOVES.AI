"""Compatibility shim for the authoritative PMOVES.YT submodule runtime."""

from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

_SUBMODULE_ROOT = pathlib.Path(__file__).resolve().parents[3] / "PMOVES.YT"
if str(_SUBMODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SUBMODULE_ROOT))

_IMPL = _SUBMODULE_ROOT / "pmoves_yt_service" / "yt.py"
__package__ = "pmoves_yt_service"
__path__ = [str(_SUBMODULE_ROOT / "pmoves_yt_service")]
code = _IMPL.read_text(encoding="utf-8")
exec(compile(code, str(_IMPL), "exec"))

if globals().get("yt_dlp") is None:
    yt_dlp = SimpleNamespace(YoutubeDL=None)
