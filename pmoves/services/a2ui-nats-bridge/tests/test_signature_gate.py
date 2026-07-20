"""CHIT signature-gate tests for the A2UI NATS bridge (consumer edge).

The bridge is the last hop before geometry reaches the frontend: with a key,
tampered packets must never be forwarded; unsigned packets forward in dev
mode and are rejected fail-closed under CHIT_REQUIRE_SIGNATURE.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "bridge.py"
SPEC = importlib.util.spec_from_file_location("pmoves.services.a2ui_nats_bridge.bridge", MODULE_PATH)
assert SPEC and SPEC.loader
bridge = importlib.util.module_from_spec(SPEC)
sys.modules["pmoves.services.a2ui_nats_bridge.bridge"] = bridge
SPEC.loader.exec_module(bridge)

from pmoves.tools.chit_security import sign_cgp  # noqa: E402

PASSPHRASE = "a2ui-test-key"


@pytest.fixture(autouse=True)
def clean_chit_env(monkeypatch):
    for var in ("CHIT_SIGNING_KEY", "CHIT_PASSPHRASE", "CHIT_REQUIRE_SIGNATURE"):
        monkeypatch.delenv(var, raising=False)


class TestSignatureGateWithKey:
    def test_valid_signature_forwarded(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        signed = sign_cgp({"spec": "chit.cgp.v0.2", "n": 1}, passphrase=PASSPHRASE)
        assert bridge.cgp_passes_signature_gate(signed) == (True, "")

    def test_tampered_always_rejected(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        tampered = sign_cgp({"spec": "chit.cgp.v0.2", "n": 1}, passphrase=PASSPHRASE)
        tampered["n"] = 2
        passes, reason = bridge.cgp_passes_signature_gate(tampered)
        assert passes is False
        assert reason == "invalid"

    def test_unsigned_forwarded_in_dev_mode(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        passes, reason = bridge.cgp_passes_signature_gate({"spec": "chit.cgp.v0.2"})
        assert passes is True
        assert reason == "unsigned"

    def test_unsigned_rejected_fail_closed(self, monkeypatch):
        monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")
        assert bridge.cgp_passes_signature_gate({"spec": "chit.cgp.v0.2"}) == (False, "unsigned")


class TestSignatureGateWithoutKey:
    def test_dev_mode_passthrough(self):
        passes, _ = bridge.cgp_passes_signature_gate({"spec": "chit.cgp.v0.2"})
        assert passes is True

    def test_fail_closed_rejects_unverifiable(self, monkeypatch):
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "1")
        assert bridge.cgp_passes_signature_gate({"spec": "chit.cgp.v0.2"}) == (False, "unverifiable")


class TestSignatureGateNonDict:
    def test_non_dict_payload_passes_in_dev_mode(self):
        assert bridge.cgp_passes_signature_gate([1, 2, 3]) == (True, "non-dict")
        assert bridge.cgp_passes_signature_gate("raw") == (True, "non-dict")

    def test_non_dict_payload_rejected_fail_closed(self, monkeypatch):
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")
        assert bridge.cgp_passes_signature_gate([1, 2, 3]) == (False, "non-dict")


# --------------------------------------------------------------------------- #
# P7 room-lifecycle envelope tests (open-room lane, 2026-07-20)
# --------------------------------------------------------------------------- #
# These tests live in this file (vs a separate test_room_envelope.py) so they
# share the same `bridge` module instance — importing bridge twice would
# duplicate-register the prometheus Counter objects and fail collection. The
# Counter() calls happen at module import time; the prometheus_client default
# registry is process-global.

import json
from typing import Any, Dict, List

import pytest


class MockWebSocket:
    """Captures every send_text / send_json call."""

    def __init__(self) -> None:
        self.sent_text: List[str] = []
        self.sent_json: List[Dict[str, Any]] = []

    async def send_text(self, text: str) -> None:
        self.sent_text.append(text)

    async def send_json(self, payload: Dict[str, Any]) -> None:
        self.sent_json.append(payload)


class MockMsg:
    """Mimics a nats-py Msg — just .subject and .data."""

    def __init__(self, subject: str, payload: Dict[str, Any]) -> None:
        self.subject = subject
        self.data = json.dumps(payload).encode("utf-8")


@pytest.fixture
def ws() -> MockWebSocket:
    return MockWebSocket()


# ---- room.session.updated.v1 ----

@pytest.mark.asyncio
async def test_room_session_handler_wraps_in_p7_rooms_envelope(ws):
    payload = {
        "v": "1.0.0",
        "room_id": "demo.room.rehearsal",
        "previous_stage": "rehearsal",
        "new_stage": "live",
        "reason": "operator approval",
        "requester": "DARKXSIDE",
        "timestamp": "2026-07-20T20:00:00Z",
        "chit": {
            "kid": None,
            "ts": "2026-07-20T20:00:00Z",
            "status": "unsigned-local",
            "signature": "",
        },
    }
    msg = MockMsg(bridge.P7_ROOM_SESSION_UPDATED_SUBJECT, payload)

    before = bridge.room_session_events_forwarded._value.get()
    await bridge.forward_room_session_event(msg, ws)
    after = bridge.room_session_events_forwarded._value.get()

    assert len(ws.sent_text) == 1
    line = ws.sent_text[0]
    assert line.endswith("\n"), "A2UI renderer expects JSONL (newline-terminated)"
    envelope = json.loads(line.rstrip("\n"))
    assert envelope["room"] == "p7-rooms"
    assert envelope["subject"] == "room.session.updated.v1"
    assert envelope["data"] == payload
    assert after - before == 1, "Prometheus counter should have incremented by 1"


@pytest.mark.asyncio
async def test_room_session_handler_respects_env_override(ws):
    # Module-level P7_WS_ROOM is read at call time inside the handler, so
    # mutating it on the module and restoring after the test is sufficient.
    original = bridge.P7_WS_ROOM
    bridge.P7_WS_ROOM = "custom-rooms"
    try:
        msg = MockMsg("room.session.updated.v1", {"room_id": "x", "new_stage": "live"})
        await bridge.forward_room_session_event(msg, ws)
        envelope = json.loads(ws.sent_text[0].rstrip("\n"))
        assert envelope["room"] == "custom-rooms"
    finally:
        bridge.P7_WS_ROOM = original


@pytest.mark.asyncio
async def test_room_session_handler_handles_garbage_payload(ws):
    """A non-JSON payload must not crash the handler; the WebSocket is
    bypassed but the bridge loop continues."""
    msg = MockMsg.__new__(MockMsg)
    msg.subject = "room.session.updated.v1"
    msg.data = b"not-valid-json"
    await bridge.forward_room_session_event(msg, ws)
    # No message forwarded (parse failed) and no exception raised
    assert ws.sent_text == []


# ---- pmoves.config.rooms.reloaded.v1 ----

@pytest.mark.asyncio
async def test_config_reloaded_handler_wraps_in_p7_rooms_envelope(ws):
    payload = {
        "v": "1.0.0",
        "schema_version": "1.2.0",
        "rooms_loaded": 9,
        "timestamp": "2026-07-20T20:00:00Z",
        "chit": {
            "kid": None,
            "ts": "2026-07-20T20:00:00Z",
            "status": "unsigned-local",
            "signature": "",
        },
    }
    msg = MockMsg(bridge.P7_CONFIG_RELOADED_SUBJECT, payload)

    before = bridge.room_config_reloaded_events_forwarded._value.get()
    await bridge.forward_config_reloaded_event(msg, ws)
    after = bridge.room_config_reloaded_events_forwarded._value.get()

    assert len(ws.sent_text) == 1
    envelope = json.loads(ws.sent_text[0].rstrip("\n"))
    assert envelope["room"] == "p7-rooms"
    assert envelope["subject"] == "pmoves.config.rooms.reloaded.v1"
    assert envelope["data"] == payload
    assert after - before == 1


@pytest.mark.asyncio
async def test_config_reloaded_handler_handles_garbage_payload(ws):
    msg = MockMsg.__new__(MockMsg)
    msg.subject = "pmoves.config.rooms.reloaded.v1"
    msg.data = b"not-valid-json"
    await bridge.forward_config_reloaded_event(msg, ws)
    assert ws.sent_text == []


# ---- subject constants (contract test) ----

def test_subject_constants_match_p7_service_spec():
    """The P7 service spec §6.3 + §6.4 defines these subjects canonically.
    A change here is a contract break — must be deliberate."""
    assert bridge.P7_ROOM_SESSION_UPDATED_SUBJECT == "room.session.updated.v1"
    assert bridge.P7_CONFIG_RELOADED_SUBJECT == "pmoves.config.rooms.reloaded.v1"


def test_p7_ws_room_default():
    """Default room name for the envelope. Frontend filters on this."""
    assert bridge.P7_WS_ROOM == "p7-rooms"
