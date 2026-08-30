"""Tests for the geometry-bus bridge (#1397).

Covers:
  - Encoded packet matches CGP v0.2 schema
  - HMAC sign+verify roundtrip
  - Vendored sign_cgp produces byte-identical output to canonical
    pmoves.tools.chit_security.sign_cgp (drift guard)
  - Dual-publish kill-switch and CGP subject env overrides
  - Missing passphrase returns unsigned packet + warning (dev mode)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# conftest.py adds the parent flute-gateway dir to sys.path; this module is
# importable as `geometry_bridge` / `chit_signing`.
from chit_signing import sign_cgp as vendored_sign_cgp
from geometry_bridge import (
    CGP_SPEC,
    GeometryBridge,
    cgp_subject,
    is_dual_publish_enabled,
)


# Add repo root to sys.path so we can import the canonical signer for the
# byte-equivalence test. This works in dev (where the test runs from a
# checked-out tree) but is correctly absent in the container (where the
# test does not run).
_repo_root = Path(__file__).resolve().parents[4]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


SAMPLE_EVENT = {
    "namespace": "pmoves.voice",
    "modality": "voice_synthesis",
    "provider": "vibevoice",
    "text_length": 142,
    "audio_duration_seconds": 8.4,
    "voice": "alloy",
    "ts": "2026-04-27T12:00:00+00:00",
}


@pytest.fixture
def passphrase(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set a fixed CHIT_PASSPHRASE for the duration of a test."""
    pw = "test-passphrase-not-a-secret"
    monkeypatch.setenv("CHIT_PASSPHRASE", pw)
    monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
    return pw


@pytest.fixture
def cgp_schema() -> dict:
    """Load the canonical CGP v0.2 schema for validation."""
    schema_path = _repo_root / "pmoves" / "contracts" / "schemas" / "geometry" / "cgp.v2.schema.json"
    with open(schema_path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Encoded packet shape
# ---------------------------------------------------------------------------

def test_encode_shape(passphrase: str) -> None:
    """The packet has the top-level structure CGP v0.2 requires."""
    bridge = GeometryBridge()
    pkt = bridge.encode_packet(SAMPLE_EVENT)

    assert pkt["spec"] == CGP_SPEC
    assert isinstance(pkt["super_nodes"], list) and len(pkt["super_nodes"]) >= 1

    sn = pkt["super_nodes"][0]
    assert sn["id"] == "voice-synthesis"
    assert isinstance(sn["constellations"], list) and len(sn["constellations"]) == 1

    cons = sn["constellations"][0]
    assert cons["id"] == "voice-events"
    assert isinstance(cons["points"], list) and len(cons["points"]) == 1

    point = cons["points"][0]
    assert point["modality"] == "voice_synthesis"
    assert point["ts"] == SAMPLE_EVENT["ts"]
    assert point["char_len"] == SAMPLE_EVENT["text_length"]
    # text_length is promoted to char_len; remaining keys land in meta
    assert point["meta"]["provider"] == "vibevoice"
    assert point["meta"]["audio_duration_seconds"] == 8.4
    assert point["meta"]["voice"] == "alloy"
    assert point["meta"]["namespace"] == "pmoves.voice"
    assert "ts" not in point["meta"]
    assert "modality" not in point["meta"]
    assert "text_length" not in point["meta"]


def test_encode_with_negative_text_length_drops_char_len(passphrase: str) -> None:
    """Defensive: malformed input doesn't crash; bad char_len is just omitted."""
    bridge = GeometryBridge()
    bad_event = {**SAMPLE_EVENT, "text_length": -1}
    pkt = bridge.encode_packet(bad_event)
    assert "char_len" not in pkt["super_nodes"][0]["constellations"][0]["points"][0]


# ---------------------------------------------------------------------------
# 2. Schema validity
# ---------------------------------------------------------------------------

def test_schema_valid(passphrase: str, cgp_schema: dict) -> None:
    """Encoded packets validate against the canonical CGP v0.2 schema."""
    jsonschema = pytest.importorskip("jsonschema")
    bridge = GeometryBridge()
    pkt = bridge.encode_packet(SAMPLE_EVENT)
    jsonschema.validate(pkt, cgp_schema)


# ---------------------------------------------------------------------------
# 3. Sign + verify roundtrip
# ---------------------------------------------------------------------------

def test_sign_verify_roundtrip(passphrase: str) -> None:
    """A signed packet verifies True with the same passphrase."""
    bridge = GeometryBridge()
    pkt = bridge.encode_packet(SAMPLE_EVENT)
    assert "sig" in pkt
    assert pkt["sig"]["alg"] == "HMAC-SHA256"
    assert bridge.verify_packet(pkt) is True


def test_verify_fails_on_tampered_packet(passphrase: str) -> None:
    """Mutating any field after signing breaks the HMAC."""
    bridge = GeometryBridge()
    pkt = bridge.encode_packet(SAMPLE_EVENT)
    pkt["super_nodes"][0]["constellations"][0]["points"][0]["meta"]["voice"] = "tampered"
    assert bridge.verify_packet(pkt) is False


# ---------------------------------------------------------------------------
# 4. Drift guard: vendored signer matches canonical byte-for-byte
# ---------------------------------------------------------------------------

def test_sign_byte_equivalence_with_canonical(passphrase: str) -> None:
    """The vendored sign_cgp must produce the same HMAC as pmoves.tools.chit_security.sign_cgp.

    This catches drift: if either signer changes its canonicalization
    or HMAC construction, this test fails and forces both to stay aligned.
    Skipped if the canonical module isn't on PYTHONPATH (shouldn't happen
    in a checked-out tree, but skip defensively for unusual envs).
    """
    try:
        from pmoves.tools.chit_security import sign_cgp as canonical_sign_cgp
    except ImportError:
        pytest.skip("canonical pmoves.tools.chit_security not importable in this env")

    payload = {"spec": CGP_SPEC, "super_nodes": [{"id": "x", "constellations": []}]}
    a = vendored_sign_cgp(payload, passphrase=passphrase, kid="fixed-kid")
    b = canonical_sign_cgp(payload, passphrase=passphrase, kid="fixed-kid")
    assert a == b, "Vendored sign_cgp diverged from canonical — fix one to match the other."


# ---------------------------------------------------------------------------
# 5. Env-driven feature flags
# ---------------------------------------------------------------------------

def test_dual_publish_default_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUTE_GEOMETRY_DUAL_PUBLISH", raising=False)
    assert is_dual_publish_enabled() is True


@pytest.mark.parametrize("val", ["false", "FALSE", "0", "no", "off"])
def test_dual_publish_kill_switch(monkeypatch: pytest.MonkeyPatch, val: str) -> None:
    monkeypatch.setenv("FLUTE_GEOMETRY_DUAL_PUBLISH", val)
    assert is_dual_publish_enabled() is False


def test_cgp_subject_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUTE_CGP_SUBJECT", raising=False)
    assert cgp_subject() == "geometry.cgp.v1"


def test_cgp_subject_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUTE_CGP_SUBJECT", "geometry.cgp.test.v1")
    assert cgp_subject() == "geometry.cgp.test.v1"


# ---------------------------------------------------------------------------
# 6. Missing-passphrase dev mode
# ---------------------------------------------------------------------------

def test_missing_passphrase_returns_unsigned_with_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Without a key, encode_packet returns unsigned + logs warning (dev mode)."""
    monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
    monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
    with caplog.at_level("WARNING"):
        bridge = GeometryBridge()
        pkt = bridge.encode_packet(SAMPLE_EVENT)
    assert "sig" not in pkt
    assert any("unsigned" in rec.message.lower() for rec in caplog.records)


def test_explicit_passphrase_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Passing passphrase to GeometryBridge() takes priority over env."""
    monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
    monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
    bridge = GeometryBridge(passphrase="ctor-passphrase")
    pkt = bridge.encode_packet(SAMPLE_EVENT)
    assert "sig" in pkt
    assert bridge.verify_packet(pkt) is True


# ---------------------------------------------------------------------------
# 7. main.py wiring — _publish_chit_voice_event dual-publish flow
# ---------------------------------------------------------------------------
#
# These tests monkeypatch module attributes on `main` directly rather than
# reloading the module — Prometheus's default Collector registry rejects
# re-registration of metrics, so reload would crash the test.


@pytest.fixture
def flute_main_module():
    """Import `main` once and yield it. Tests monkeypatch attributes on it."""
    import main as flute_main
    return flute_main


@pytest.mark.asyncio
async def test_publish_voice_event_publishes_to_both_subjects(
    monkeypatch: pytest.MonkeyPatch, passphrase: str, flute_main_module
) -> None:
    """When CHIT_VOICE_ATTRIBUTION=true and dual-publish enabled, both
    legacy and canonical subjects receive a publish."""
    monkeypatch.delenv("FLUTE_GEOMETRY_DUAL_PUBLISH", raising=False)
    monkeypatch.setattr(flute_main_module, "CHIT_VOICE_ATTRIBUTION", True)

    published: list[tuple[str, bytes]] = []

    class StubNats:
        async def publish(self, subject: str, payload: bytes) -> None:
            published.append((subject, payload))

    monkeypatch.setattr(flute_main_module, "nats_client", StubNats())
    monkeypatch.setattr(flute_main_module, "geometry_bridge", None)

    await flute_main_module._publish_chit_voice_event(
        provider="vibevoice", text_length=42, audio_duration=2.5, voice="alloy"
    )

    subjects = [s for s, _ in published]
    assert "tokenism.geometry.event.v1" in subjects
    assert "geometry.cgp.v1" in subjects
    assert len(published) == 2

    # Canonical packet must validate as a signed CGP
    canonical_payload = next(p for s, p in published if s == "geometry.cgp.v1")
    pkt = json.loads(canonical_payload)
    assert pkt["spec"] == CGP_SPEC
    assert pkt["sig"]["alg"] == "HMAC-SHA256"


@pytest.mark.asyncio
async def test_publish_voice_event_kill_switch_skips_canonical(
    monkeypatch: pytest.MonkeyPatch, passphrase: str, flute_main_module
) -> None:
    """FLUTE_GEOMETRY_DUAL_PUBLISH=false skips the canonical publish but
    still emits the legacy event."""
    monkeypatch.setenv("FLUTE_GEOMETRY_DUAL_PUBLISH", "false")
    monkeypatch.setattr(flute_main_module, "CHIT_VOICE_ATTRIBUTION", True)

    published: list[tuple[str, bytes]] = []

    class StubNats:
        async def publish(self, subject: str, payload: bytes) -> None:
            published.append((subject, payload))

    monkeypatch.setattr(flute_main_module, "nats_client", StubNats())
    monkeypatch.setattr(flute_main_module, "geometry_bridge", None)

    await flute_main_module._publish_chit_voice_event(
        provider="vibevoice", text_length=42, audio_duration=2.5, voice="alloy"
    )

    subjects = [s for s, _ in published]
    assert "tokenism.geometry.event.v1" in subjects
    assert "geometry.cgp.v1" not in subjects
    assert len(published) == 1


@pytest.mark.asyncio
async def test_publish_voice_event_disabled_attribution_skips_both(
    monkeypatch: pytest.MonkeyPatch, passphrase: str, flute_main_module
) -> None:
    """CHIT_VOICE_ATTRIBUTION=false (module-level) skips ALL publishes."""
    monkeypatch.setattr(flute_main_module, "CHIT_VOICE_ATTRIBUTION", False)

    published: list[tuple[str, bytes]] = []

    class StubNats:
        async def publish(self, subject: str, payload: bytes) -> None:
            published.append((subject, payload))

    monkeypatch.setattr(flute_main_module, "nats_client", StubNats())

    await flute_main_module._publish_chit_voice_event(
        provider="vibevoice", text_length=42, audio_duration=2.5, voice="alloy"
    )

    assert published == []
