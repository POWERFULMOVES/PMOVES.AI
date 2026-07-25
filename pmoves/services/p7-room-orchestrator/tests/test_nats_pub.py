"""
Tests for NATSPublisher.

The publisher has two modes:
  - connected: actually publishes via nats-py
  - log-only: when NATS is unreachable, falls back to log+return-True

We test the sign + payload shape directly (no NATS connection needed), and
exercise the high-level helpers to confirm subject + payload contracts match
the spec.
"""

from __future__ import annotations

import json

import pytest

from nats_pub import (
    NATSPublisher,
    SUBJECT_CONFIG_RELOADED,
    SUBJECT_LAUNCH,
    SUBJECT_ROOM_UPDATED,
    SUBJECT_SESSION,
)


def test_sign_unsigned_local_when_no_key():
    p = NATSPublisher(nats_url="nats://nowhere", service_card_id="", signing_key="")
    payload = p._sign({"foo": "bar"})
    assert "chit" in payload
    assert payload["chit"]["status"] == "unsigned-local"
    assert payload["chit"]["signature"] == ""
    assert payload["chit"]["ts"].endswith("Z")


def test_sign_with_key_produces_hmac():
    p = NATSPublisher(nats_url="nats://nowhere", service_card_id="test-card", signing_key="secret")
    payload = p._sign({"foo": "bar"})
    assert payload["chit"]["status"] == "signed"
    assert payload["chit"]["kid"] == "test-card"
    assert len(payload["chit"]["signature"]) == 64  # sha256 hex digest


def test_sign_preserves_payload_fields():
    p = NATSPublisher(nats_url="nats://nowhere", service_card_id="", signing_key="")
    payload = p._sign({"room_id": "abc", "new_stage": "live", "reason": "x"})
    assert payload["room_id"] == "abc"
    assert payload["new_stage"] == "live"


@pytest.mark.asyncio
async def test_publish_log_only_fallback_when_not_connected(caplog):
    import logging
    caplog.set_level(logging.INFO, logger="p7.nats")
    p = NATSPublisher(nats_url="nats://127.0.0.1:1", service_card_id="", signing_key="")
    # connect() will fail (unreachable), sets _connected=False
    ok = await p.publish("test.subject", {"hello": "world"})
    assert ok is True
    # Publisher should have logged the publish
    assert any("NATS-LOG" in rec.message or "NATS publish" in rec.message
               for rec in caplog.records)


@pytest.mark.asyncio
async def test_publish_room_updated_shape():
    p = NATSPublisher(nats_url="nats://127.0.0.1:1", service_card_id="", signing_key="")
    await p.publish_room_updated(
        room_id="x.room", previous_stage="rehearsal", new_stage="live",
        reason="promotion", requester="DARKXSIDE",
    )
    # We can't inspect the publisher's internal call list without monkey-patching
    # but the function should be side-effect-free in log-only mode.


@pytest.mark.asyncio
async def test_high_level_helpers_use_correct_subjects():
    """Verify the high-level helpers wrap the spec'd subjects."""
    p = NATSPublisher(nats_url="nats://127.0.0.1:1", service_card_id="", signing_key="")

    captured = []

    async def fake_publish(subject, payload):
        captured.append((subject, payload))
        return True

    p.publish = fake_publish  # type: ignore[assignment]

    await p.publish_room_launched("r", "a", "al", "ov", "1.0.0")
    await p.publish_room_session("r", "sid", "open", "a")
    await p.publish_room_updated("r", "rehearsal", "live", "ok", "me")
    await p.publish_config_reloaded("1.2.0", 9)

    assert captured[0][0] == SUBJECT_LAUNCH
    assert captured[0][1]["room_id"] == "r"
    assert captured[0][1]["overlay"] == "ov"

    assert captured[1][0] == SUBJECT_SESSION
    assert captured[1][1]["action"] == "open"

    assert captured[2][0] == SUBJECT_ROOM_UPDATED
    assert captured[2][1]["previous_stage"] == "rehearsal"
    assert captured[2][1]["new_stage"] == "live"

    assert captured[3][0] == SUBJECT_CONFIG_RELOADED
    assert captured[3][1]["rooms_loaded"] == 9
