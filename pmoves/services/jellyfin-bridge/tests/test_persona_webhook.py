"""Tests for the jellyfin-bridge persona playback producer."""

import importlib.util
import sys
import time
from pathlib import Path

import pytest

# Bridge main.py lives one level up and imports its sibling modules
# (tac_tree) by name — the service dir must be on sys.path DURING exec,
# then comes off again: leaving it pollutes the all-services suite, where
# another service's bare `import main` would re-execute the bridge and
# double-register its prometheus counters (DuplicateTimeseries).
_SERVICE_DIR = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, _SERVICE_DIR)
try:
    _spec = importlib.util.spec_from_file_location(
        "jellyfin_bridge_main", Path(_SERVICE_DIR) / "main.py"
    )
    bridge = importlib.util.module_from_spec(_spec)
    sys.modules["jellyfin_bridge_main"] = bridge
    _spec.loader.exec_module(bridge)
finally:
    sys.path.remove(_SERVICE_DIR)


def _payload(ntype, user="DARKXSIDE", item="track-1", itype="Audio", **over):
    body = {
        "NotificationType": ntype,
        "UserName": user,
        "ItemId": item,
        "ItemType": itype,
        "SessionId": "sess-1",
    }
    body.update(over)
    return body


def test_playback_start_builds_human_event():
    ev = bridge._build_persona_event(_payload("PlaybackStart"))
    assert ev["consumer_kind"] == "human"
    assert ev["user_id"] == "darkxside"
    assert ev["item_kind"] == "beat"
    assert ev["source"] == "jellyfin"
    assert ev["item_id"] == "track-1"


def test_non_audio_maps_to_generic():
    ev = bridge._build_persona_event(_payload("PlaybackStart", itype="Movie"))
    assert ev["item_kind"] == "generic"


def test_stop_carries_duration_after_start():
    bridge._build_persona_event(_payload("PlaybackStart"))
    time.sleep(0.05)
    ev = bridge._build_persona_event(_payload("PlaybackStop"))
    assert ev["duration_seconds"] >= 0.05


def test_unknown_notification_dropped():
    assert bridge._build_persona_event(_payload("UserDataSaved")) is None


def test_missing_user_dropped():
    assert bridge._build_persona_event(_payload("PlaybackStart", user="")) is None


def test_user_map_override(monkeypatch):
    monkeypatch.setenv("PERSONA_THIRDREF_JELLYFIN_USER_MAP", '{"DJ":"darkxside-dj"}')
    ev = bridge._build_persona_event(_payload("PlaybackStart", user="DJ"))
    assert ev["user_id"] == "darkxside-dj"


def test_invalid_user_map_json_degrades(monkeypatch):
    monkeypatch.setenv("PERSONA_THIRDREF_JELLYFIN_USER_MAP", "{not json")
    ev = bridge._build_persona_event(_payload("PlaybackStart", user="DJ"))
    assert ev["user_id"] == "dj"


@pytest.mark.asyncio
async def test_publish_persona_event_failure_counts(monkeypatch):
    """A dead NATS must not raise — the webhook stays best-effort."""
    class DeadNats:
        async def connect(self, servers=None):
            raise OSError("no bus")

        async def close(self):
            pass

    import nats.aio.client as nats_mod
    monkeypatch.setattr(nats_mod, "Client", DeadNats)
    ok = await bridge._publish_persona_event({"consumer_kind": "human"})
    assert ok is False
