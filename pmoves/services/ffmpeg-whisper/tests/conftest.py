"""Pytest configuration for ffmpeg-whisper tests.

Mirrors the flute-gateway pattern: adds the service dir + the pmoves root to
sys.path so `services.common.*` resolves, sets test-only env defaults, and
stubs the heavy `services.common.supabase` module-level import.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_PMOVES_ROOT = _SERVICE_DIR.parents[1]
for _p in (str(_SERVICE_DIR), str(_PMOVES_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("NATS_URL", "nats://test@localhost:4222")
os.environ.setdefault("FFW_CGP_PUBLISH", "false")
os.environ.setdefault("FFW_CONTENT_RAW_PUBLISH", "false")

# Stub services.common.supabase before server.py imports it at module load.
# The real module instantiates a Supabase client at import time, which is not
# available in unit-test environments.
if "services.common.supabase" not in sys.modules:
    _stub = types.ModuleType("services.common.supabase")
    _stub.insert_segments = lambda rows: None  # type: ignore[attr-defined]
    sys.modules["services.common.supabase"] = _stub
