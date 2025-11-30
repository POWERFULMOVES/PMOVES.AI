"""Shim module to re-export FastAPI app from hyphenated folder.

Allows `from pmoves.services.pmoves_yt import yt as ytmod` in tests.
"""
from __future__ import annotations

import pathlib

_IMPL = pathlib.Path(__file__).resolve().parent.parent / "pmoves-yt" / "yt.py"
code = _IMPL.read_text(encoding="utf-8")
exec(compile(code, str(_IMPL), "exec"))

