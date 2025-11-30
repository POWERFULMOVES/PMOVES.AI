"""
Lightweight CHIT helpers for PMOVES.

This module exposes helper utilities that build and decode CHIT Geometry
Packets (CGP) for simple data payloads such as secret key/value pairs.  The
implementation intentionally mirrors the v0.1 CGP specification documented in
`pmoves/docs/PMOVESCHIT/PMOVESCHIT.md` so operators can script encode/decode
flows without copying snippets out of the documentation.
"""

from .codec import encode_secret_map, decode_secret_map, load_cgp  # noqa: F401

__all__ = ["encode_secret_map", "decode_secret_map", "load_cgp"]

