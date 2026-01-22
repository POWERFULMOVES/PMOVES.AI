from __future__ import annotations

from pathlib import Path
import sys
import types

import pytest


pytest.importorskip("fastapi")


if "yt_dlp" not in sys.modules:
    yt_dlp_mod = types.ModuleType("yt_dlp")

    class _PlaceholderYDL:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("yt_dlp not installed; tests should patch YoutubeDL")

    yt_dlp_mod.YoutubeDL = _PlaceholderYDL
    sys.modules["yt_dlp"] = yt_dlp_mod


if "boto3" not in sys.modules:
    boto3_mod = types.ModuleType("boto3")

    def _client(*args, **kwargs):  # pragma: no cover - defensive stub
        raise RuntimeError("boto3 client unavailable in tests")

    boto3_mod.client = _client
    sys.modules["boto3"] = boto3_mod


if "nats" not in sys.modules:
    nats_mod = types.ModuleType("nats")
    aio_mod = types.ModuleType("nats.aio")
    client_mod = types.ModuleType("nats.aio.client")

    class _DummyNATS:
        async def publish(self, *args, **kwargs):
            return None

    client_mod.Client = _DummyNATS
    aio_mod.client = client_mod
    nats_mod.aio = types.SimpleNamespace(client=client_mod)

    sys.modules["nats"] = nats_mod
    sys.modules["nats.aio"] = aio_mod
    sys.modules["nats.aio.client"] = client_mod


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Import lazily so individual tests can access shared helpers without
# re-running the path manipulation in each module.
yt = __import__("yt")


__all__ = ["yt"]
