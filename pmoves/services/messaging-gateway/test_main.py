from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


_CACHED_MODULE = None


def _load_main_module():
    global _CACHED_MODULE
    if _CACHED_MODULE is not None:
        return _CACHED_MODULE

    platforms_pkg = ModuleType("platforms")
    discord_mod = ModuleType("platforms.discord")
    telegram_mod = ModuleType("platforms.telegram")
    whatsapp_mod = ModuleType("platforms.whatsapp")

    class _Platform:
        def __init__(self, *args, **kwargs):
            pass

        async def initialize(self):
            return None

        def is_configured(self):
            return True

        def verify_signature(self, signature, timestamp, body):
            return True

        async def handle_interaction(self, payload):
            return {"ok": True, "passthrough": True}

        async def handle_update(self, payload):
            return {"ok": True}

        async def send(self, **kwargs):
            return True

    discord_mod.DiscordPlatform = _Platform
    telegram_mod.TelegramPlatform = _Platform
    whatsapp_mod.WhatsAppPlatform = _Platform
    sys.modules["platforms"] = platforms_pkg
    sys.modules["platforms.discord"] = discord_mod
    sys.modules["platforms.telegram"] = telegram_mod
    sys.modules["platforms.whatsapp"] = whatsapp_mod

    module_path = Path(__file__).resolve().parent / "main.py"
    spec = importlib.util.spec_from_file_location("messaging_gateway_main_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    _CACHED_MODULE = module
    return module


def test_handle_ytcontrol_interaction_approve(monkeypatch):
    module = _load_main_module()
    requests_made = []

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "processed": 1,
                "reason": "approved from Discord",
                "actions": [{"summary": "Playlist add: add vid-123 to playlist PL123", "notebook_entry_id": "nb-1"}],
            }

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            requests_made.append((url, headers, json))
            return DummyResponse()

    monkeypatch.setattr(module.httpx, "AsyncClient", DummyAsyncClient)
    monkeypatch.setattr(module, "CHANNEL_MONITOR_URL", "http://channel-monitor:8097")
    monkeypatch.setattr(module, "CHANNEL_MONITOR_SECRET", "secret-token")

    payload = {
        "type": 3,
        "data": {"custom_id": "ytcontrol:approve:11111111-1111-1111-1111-111111111111"},
        "member": {"user": {"username": "tester", "id": "42"}},
    }

    response = module.asyncio.run(module._handle_ytcontrol_interaction(payload))

    assert response["type"] == 4
    assert "Approved YouTube control request" in response["data"]["content"]
    assert "Playlist add" in response["data"]["content"]
    assert "Notebook: `nb-1`" in response["data"]["content"]
    assert requests_made[0][0] == "http://channel-monitor:8097/api/monitor/youtube-control/review"
    assert requests_made[0][1]["X-Channel-Monitor-Token"] == "secret-token"
    assert requests_made[0][2]["approve"] is True
    assert requests_made[0][2]["actor"] == "tester:42"


def test_handle_ytcontrol_interaction_reject(monkeypatch):
    module = _load_main_module()

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "processed": 1,
                "reason": "rejected from Discord",
                "actions": [{"summary": "Comment create: reply on vid-123"}],
            }

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            return DummyResponse()

    monkeypatch.setattr(module.httpx, "AsyncClient", DummyAsyncClient)

    payload = {
        "type": 3,
        "data": {"custom_id": "ytcontrol:reject:22222222-2222-2222-2222-222222222222"},
        "user": {"id": "77"},
    }

    response = module.asyncio.run(module._handle_ytcontrol_interaction(payload))

    assert response["type"] == 4
    assert "Rejected YouTube control request" in response["data"]["content"]
    assert "Comment create" in response["data"]["content"]
