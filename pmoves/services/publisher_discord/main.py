"""Shim module that forwards to the hyphenated package implementation.

Some tests import `pmoves.services.publisher_discord.main`, but the implementation
lives in `pmoves/services/publisher-discord/main.py`. This shim executes that file
in this module's namespace to provide a stable import path without altering the
runtime package layout used by Docker images.
"""
from __future__ import annotations

import pathlib

_IMPL = pathlib.Path(__file__).resolve().parent.parent / "publisher-discord" / "main.py"
code = _IMPL.read_text(encoding="utf-8")
exec(compile(code, str(_IMPL), "exec"))

