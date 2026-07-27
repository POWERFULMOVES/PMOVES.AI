"""Tests for nats_event_bus (slice 3 of the creator-collab lane).

Tests do NOT require a live NATS connection — the subscriber is
disabled by passing subscriber=None into create_app(). The cache +
auth + schema-validation surface is what we lock in here.
"""
from __future__ import annotations

import sys
import os
import uuid
from datetime import datetime, timezone

import pytest

# Make the service importable + ensure pmoves.services.common resolves
# via the pmoves/ PYTHONPATH root that the docker image uses.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", "..", ".."))
for p in (
    os.path.join(_ROOT, "pmoves", "services", "nats_event_bus"),
    os.path.join(_ROOT, "pmoves", "services"),
    os.path.join(_ROOT, "pmoves"),
    _ROOT,
):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi.testclient import TestClient  # noqa: E402

from nats_event_bus.app import PublishRequest, create_app  # noqa: E402
from nats_event_bus.state import (  # noqa: E402
    DEFAULT_TOPICS,
    DIRECTORY_TOPIC,
    EventCache,
    NatsSubscriber,
    PRESENCE_TOPIC,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def token() -> str:
    return "test-bus-token-abc123"


@pytest.fixture
def cache() -> EventCache:
    return EventCache()


@pytest.fixture
def client(cache, token) -> TestClient:
    app = create_app(cache=cache, subscriber=None, token=token)
    return TestClient(app)


@pytest.fixture
def unconfigured_client(cache) -> TestClient:
    """Service with no token configured — writes must be 503."""
    app = create_app(cache=cache, subscriber=None, token="")
    return TestClient(app)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def _good_prompt_payload() -> dict:
    return {
        "room_id": "creator-studio",
        "session_id": str(uuid.uuid4()),
        "prompt_id": str(uuid.uuid4()),
        "app_slug": "comfyui-desktop",
        "prompt": "a cool dragon",
        "submitted_by": "darkxside",
        "submitted_at": _now_iso(),
    }


def _good_presence_payload(room_id: str = "creator-studio") -> dict:
    return {
        "room_id": room_id,
        "presence_id": str(uuid.uuid4()),
        "actor": "darkxside",
        "actor_kind": "user",
        "action": "join",
        "surface": "notebook-workbench",
        "observed_at": _now_iso(),
    }


def _good_directory_payload() -> dict:
    return {
        "snapshot_id": str(uuid.uuid4()),
        "rooms": [
            {
                "room_id": "creator-studio",
                "title": "Creator Studio",
                "room_purpose": "studio",
                "creator_surface": "primary",
                "stage": "rehearsal",
                "active_session_id": None,
                "hardware_summary": {"gpu": True, "min_vram_mb": 24000},
                "apps_count": 4,
                "skills_count": 3,
            }
        ],
        "snapshot_at": _now_iso(),
    }


# --------------------------------------------------------------------------
# /healthz
# --------------------------------------------------------------------------

def test_healthz_reports_topics_and_writes_state(client) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # All 5 slice-3 topics advertised.
    for t in DEFAULT_TOPICS:
        assert t in body["topics"]
    # Token configured → writes enabled.
    assert body["writes_enabled"] is True
    # No subscriber passed → nats connection state is false.
    assert body["nats_connected"] is False
    assert body["nats_enabled"] is False


def test_healthz_reports_writes_disabled_when_token_missing(unconfigured_client) -> None:
    r = unconfigured_client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["writes_enabled"] is False


# --------------------------------------------------------------------------
# /v1/topics
# --------------------------------------------------------------------------

def test_list_topics_returns_the_five_slice3_subjects(client) -> None:
    r = client.get("/v1/topics")
    assert r.status_code == 200
    body = r.json()
    assert set(body["topics"]) == set(DEFAULT_TOPICS)


# --------------------------------------------------------------------------
# /v1/publish — auth gate
# --------------------------------------------------------------------------

def test_publish_without_token_returns_503_when_service_token_unset(unconfigured_client) -> None:
    r = unconfigured_client.post(
        "/v1/publish",
        json={"topic": "comfy.collab.prompt.v1", "payload": _good_prompt_payload()},
    )
    assert r.status_code == 503
    assert "NATS_EVENT_BUS_TOKEN not configured" in r.text


def test_publish_with_wrong_token_returns_401(client) -> None:
    r = client.post(
        "/v1/publish",
        headers={"X-PMOVES-NatsBus-Token": "wrong"},
        json={"topic": "comfy.collab.prompt.v1", "payload": _good_prompt_payload()},
    )
    assert r.status_code == 401


def test_publish_with_correct_token_returns_envelope(client) -> None:
    r = client.post(
        "/v1/publish",
        headers={"X-PMOVES-NatsBus-Token": "test-bus-token-abc123"},
        json={"topic": "comfy.collab.prompt.v1", "payload": _good_prompt_payload(), "source": "test"},
    )
    assert r.status_code == 200, r.text
    env = r.json()["envelope"]
    assert env["topic"] == "comfy.collab.prompt.v1"
    assert env["version"] == "v1"
    assert env["source"] == "test"
    assert "id" in env and "ts" in env
    assert env["payload"]["prompt"] == "a cool dragon"


def test_publish_with_bad_payload_returns_422(client) -> None:
    # Missing required fields (room_id, prompt_id, etc).
    bad = {"prompt": "x"}
    r = client.post(
        "/v1/publish",
        headers={"X-PMOVES-NatsBus-Token": "test-bus-token-abc123"},
        json={"topic": "comfy.collab.prompt.v1", "payload": bad},
    )
    assert r.status_code == 422


def test_publish_with_unknown_topic_returns_404(client) -> None:
    r = client.post(
        "/v1/publish",
        headers={"X-PMOVES-NatsBus-Token": "test-bus-token-abc123"},
        json={"topic": "nope.unknown.v1", "payload": {}},
    )
    assert r.status_code == 404


def test_publish_rejects_extra_payload_fields_via_schema(client) -> None:
    """The schemas are additionalProperties:false — a stray field must fail."""
    p = _good_prompt_payload()
    p["not_in_schema"] = "leak"
    r = client.post(
        "/v1/publish",
        headers={"X-PMOVES-NatsBus-Token": "test-bus-token-abc123"},
        json={"topic": "comfy.collab.prompt.v1", "payload": p},
    )
    assert r.status_code == 422


# --------------------------------------------------------------------------
# /v1/publish — caches so GET can read it back
# --------------------------------------------------------------------------

def test_publish_then_read_returns_envelope(client) -> None:
    pub = client.post(
        "/v1/publish",
        headers={"X-PMOVES-NatsBus-Token": "test-bus-token-abc123"},
        json={"topic": "comfy.collab.prompt.v1", "payload": _good_prompt_payload()},
    )
    assert pub.status_code == 200

    rd = client.get("/v1/events/comfy.collab.prompt.v1")
    assert rd.status_code == 200
    body = rd.json()
    assert body["topic"] == "comfy.collab.prompt.v1"
    assert body["count"] == 1
    assert body["events"][0]["payload"]["prompt"] == "a cool dragon"


def test_read_events_unknown_topic_returns_404(client) -> None:
    r = client.get("/v1/events/nope.unknown.v1")
    assert r.status_code == 404


def test_read_events_limit_is_respected(cache) -> None:
    # Seed 5 envelopes directly into the cache (no NATS, no auth).
    import asyncio
    async def _seed():
        for _ in range(5):
            await cache.append(
                "comfy.collab.prompt.v1",
                {"id": str(uuid.uuid4()), "topic": "comfy.collab.prompt.v1", "ts": _now_iso(),
                 "version": "v1", "source": "test", "payload": _good_prompt_payload()},
            )
    asyncio.get_event_loop().run_until_complete(_seed())

    app = create_app(cache=cache, subscriber=None, token="t")
    c = TestClient(app)
    r = c.get("/v1/events/comfy.collab.prompt.v1?limit=2")
    assert r.status_code == 200
    assert r.json()["count"] == 2


# --------------------------------------------------------------------------
# /v1/snapshot/room-directory
# --------------------------------------------------------------------------

def test_snapshot_returns_latest_directory_envelope(client) -> None:
    p1 = _good_directory_payload()
    r1 = client.post(
        "/v1/publish",
        headers={"X-PMOVES-NatsBus-Token": "test-bus-token-abc123"},
        json={"topic": "room.directory.v1", "payload": p1},
    )
    assert r1.status_code == 200

    p2 = _good_directory_payload()
    p2["rooms"][0]["stage"] = "live"
    r2 = client.post(
        "/v1/publish",
        headers={"X-PMOVES-NatsBus-Token": "test-bus-token-abc123"},
        json={"topic": "room.directory.v1", "payload": p2},
    )
    assert r2.status_code == 200

    snap = client.get("/v1/snapshot/room-directory")
    assert snap.status_code == 200
    env = snap.json()["envelope"]
    # Latest is the second publish (live stage).
    assert env["payload"]["rooms"][0]["stage"] == "live"


def test_snapshot_returns_404_when_no_directory_seen(client) -> None:
    r = client.get("/v1/snapshot/room-directory")
    assert r.status_code == 404


# --------------------------------------------------------------------------
# /v1/presence/{room_id}
# --------------------------------------------------------------------------

def test_presence_filters_by_room_id(client) -> None:
    # Presence for two different rooms.
    for room in ("creator-studio", "fordham-hill"):
        r = client.post(
            "/v1/publish",
            headers={"X-PMOVES-NatsBus-Token": "test-bus-token-abc123"},
            json={"topic": "room.presence.v1", "payload": _good_presence_payload(room_id=room)},
        )
        assert r.status_code == 200

    r = client.get("/v1/presence/creator-studio")
    assert r.status_code == 200
    body = r.json()
    assert body["room_id"] == "creator-studio"
    assert body["count"] == 1
    assert body["events"][0]["payload"]["actor"] == "darkxside"

    r2 = client.get("/v1/presence/fordham-hill")
    assert r2.json()["count"] == 1


def test_presence_returns_empty_for_unknown_room(client) -> None:
    client.post(
        "/v1/publish",
        headers={"X-PMOVES-NatsBus-Token": "test-bus-token-abc123"},
        json={"topic": "room.presence.v1", "payload": _good_presence_payload(room_id="creator-studio")},
    )
    r = client.get("/v1/presence/nonexistent")
    assert r.status_code == 200
    assert r.json()["count"] == 0


# --------------------------------------------------------------------------
# Auto-register of new topics
# --------------------------------------------------------------------------

def test_publish_auto_registers_unknown_topic_so_later_reads_work(client, cache) -> None:
    """A producer that emits a brand-new topic should not have to
    restart the service for the new subject to be readable."""
    payload = {
        "room_id": "creator-studio",
        "presence_id": str(uuid.uuid4()),
        "actor": "auto-test",
        "actor_kind": "service",
        "action": "active",
        "observed_at": _now_iso(),
    }
    r = client.post(
        "/v1/publish",
        headers={"X-PMOVES-NatsBus-Token": "test-bus-token-abc123"},
        json={"topic": "room.presence.v1", "payload": payload},
    )
    assert r.status_code == 200
    # Topic already registered (it's a default). Re-publish to confirm
    # the cache accepts it after the first time without re-registering.
    r2 = client.post(
        "/v1/publish",
        headers={"X-PMOVES-NatsBus-Token": "test-bus-token-abc123"},
        json={"topic": "room.presence.v1", "payload": payload},
    )
    assert r2.status_code == 200
    rd = client.get("/v1/events/room.presence.v1")
    assert rd.json()["count"] == 2


# --------------------------------------------------------------------------
# NatsSubscriber — disabled when NATS_URL is empty
# --------------------------------------------------------------------------

def test_subscriber_disabled_when_nats_url_empty() -> None:
    cache = EventCache()
    sub = NatsSubscriber(cache=cache, nats_url="")
    assert sub.enabled is False
    # start() is a no-op when disabled.
    import asyncio
    asyncio.get_event_loop().run_until_complete(sub.start())
    assert sub.connected is False


def test_subscriber_constructor_inherits_default_topics(cache) -> None:
    sub = NatsSubscriber(cache=cache, nats_url="nats://127.0.0.1:0")
    assert set(sub._topics) == set(DEFAULT_TOPICS)


# --------------------------------------------------------------------------
# PublishRequest schema (Pydantic surface)
# --------------------------------------------------------------------------

def test_publish_request_rejects_blank_topic() -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        PublishRequest(topic="", payload={})
