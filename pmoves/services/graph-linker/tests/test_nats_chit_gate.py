"""Tests for the CHIT signature gate in the graph-linker NATS handler.

Closes the THIRD_ANCHOR gap: sign_neo4j_node produced signatures but no
consumer verified them. These tests assert the consumer-edge contract:
- with a key, tampered payloads are ALWAYS rejected to dead-letter;
- unsigned payloads pass in dev mode;
- unsigned payloads are rejected fail-closed under CHIT_REQUIRE_SIGNATURE;
- when the signing subsystem is off (CHIT_SIGN_NEO4J=false), gate passes
  through unless fail-closed is demanded.

No importlib.reload: reloading nats_handler would rebind the module-global
``counters`` instance that the pre-existing test_nats_handler.py suite holds
a reference to. Env state is monkeypatched per-test instead.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nats_handler as nh  # noqa: E402
import chit_signer as cs  # noqa: E402

from pmoves.tools.chit_security import sign_cgp  # noqa: E402

PASSPHRASE = "graph-linker-test-key"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in (
        "CHIT_SIGNING_KEY",
        "CHIT_PASSPHRASE",
        "CHIT_SIGN_NEO4J",
        "CHIT_REQUIRE_SIGNATURE",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def _refresh_gate_state(monkeypatch):
    """Keep module-level gate constants in sync with the (cleared) env."""
    monkeypatch.setattr(cs, "CHIT_SIGN_NEO4J", False)
    monkeypatch.setattr(nh, "CHIT_SIGN_NEO4J", False)
    yield
    monkeypatch.setattr(cs, "CHIT_SIGN_NEO4J", False)
    monkeypatch.setattr(nh, "CHIT_SIGN_NEO4J", False)


def _enable_signing(monkeypatch):
    monkeypatch.setenv("CHIT_SIGN_NEO4J", "true")
    monkeypatch.setenv("CHIT_PASSPHRASE", PASSPHRASE)
    monkeypatch.setattr(cs, "CHIT_SIGN_NEO4J", True)
    monkeypatch.setattr(nh, "CHIT_SIGN_NEO4J", True)
    # _CHIT_SIGNING_KEY is captured at import time — patch it directly
    monkeypatch.setattr(cs, "_CHIT_SIGNING_KEY", PASSPHRASE)


def _handler():
    return nh.NATSHandler.__new__(nh.NATSHandler)


class TestSignatureGate:
    def test_valid_signature_passes(self, monkeypatch):
        _enable_signing(monkeypatch)
        signed = sign_cgp({"id": "a1", "label": "Image"}, passphrase=PASSPHRASE)
        assert _handler()._signature_gate(signed) == (True, "")

    def test_tampered_always_rejected(self, monkeypatch):
        _enable_signing(monkeypatch)
        signed = sign_cgp({"id": "a2", "label": "Image"}, passphrase=PASSPHRASE)
        signed["label"] = "Tampered"
        assert _handler()._signature_gate(signed) == (False, "invalid")

    def test_unsigned_passes_in_dev_mode(self, monkeypatch):
        _enable_signing(monkeypatch)
        assert _handler()._signature_gate({"id": "a3"}) == (True, "unsigned")

    def test_unsigned_rejected_fail_closed(self, monkeypatch):
        _enable_signing(monkeypatch)
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")
        assert _handler()._signature_gate({"id": "a4"}) == (False, "unsigned")

    def test_signing_off_passthrough_unless_fail_closed(self, monkeypatch):
        h = _handler()
        assert h._signature_gate({"id": "x"}) == (True, "unverifiable")
        monkeypatch.setenv("CHIT_REQUIRE_SIGNATURE", "true")
        assert h._signature_gate({"id": "x"}) == (False, "unverifiable")


class TestHandleMessageGate:
    """End-to-end: an envelope with a tampered data payload is dead-lettered,
    never written to Neo4j."""

    @pytest.mark.asyncio
    async def test_tampered_envelope_dead_lettered(self, monkeypatch):
        _enable_signing(monkeypatch)
        handler = _handler()
        dead_letters = []

        async def _fake_dead_letter(subject, msg, error):
            dead_letters.append((subject, error))

        monkeypatch.setattr(handler, "_publish_dead_letter", _fake_dead_letter)

        signed = sign_cgp(
            {"uri": "s3://b/k", "evt_id": "e1"}, passphrase=PASSPHRASE
        )
        signed["uri"] = "s3://evil/swap"
        raw = json.dumps({"topic": "gen.image.result.v1", "id": "evt-1", "ts": "2026-09-12T00:00:00Z", "source": "comfyui-agent", "payload": signed}).encode()

        class _Msg:
            data = raw

        await handler._handle_message("gen.image.result.v1", _Msg())
        assert len(dead_letters) == 1
        assert "invalid" in dead_letters[0][1]

    @pytest.mark.asyncio
    async def test_valid_envelope_reaches_routing(self, monkeypatch):
        _enable_signing(monkeypatch)
        handler = _handler()
        dead_letters = []

        async def _fake_dead_letter(subject, msg, error):
            dead_letters.append((subject, error))

        monkeypatch.setattr(handler, "_publish_dead_letter", _fake_dead_letter)
        routed = []
        def _recorder(parsed):
            routed.append(parsed)

        neo4j_stub = type("Recorder", (), {})()
        neo4j_stub.handle_gen_image_result = _recorder
        handler._neo4j = neo4j_stub  # instance attr (handler built via __new__)

        signed = sign_cgp(
            {"uri": "s3://b/k", "evt_id": "e1"}, passphrase=PASSPHRASE
        )
        raw = json.dumps({"topic": "gen.image.result.v1", "id": "evt-1", "ts": "2026-09-12T00:00:00Z", "source": "comfyui-agent", "payload": signed}).encode()

        class _Msg:
            data = raw

        await handler._handle_message("gen.image.result.v1", _Msg())
        assert not dead_letters
        assert routed

    @pytest.mark.asyncio
    async def test_non_json_still_raises_to_dead_letter(self, monkeypatch):
        """Gate must not swallow malformed messages — they die in the
        existing envelope-validation path, not the signature gate."""
        handler = _handler()
        dead_letters = []

        async def _fake_dead_letter(subject, msg, error):
            dead_letters.append((subject, error))

        monkeypatch.setattr(handler, "_publish_dead_letter", _fake_dead_letter)

        class _Msg:
            data = b"not-json{"

        with pytest.raises(Exception):
            await handler._handle_message("gen.image.result.v1", _Msg())
