"""
Tests for the FastAPI app.

Uses FastAPI TestClient. The lifespan handler creates a real CatalogLoader
against the hermetic temp pmoves/ subtree and a log-only NATSPublisher.
We swap in a FakePublisher post-startup so we can assert publish calls.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _patch_publisher_after_lifespan(monkeypatch):
    """
    After the lifespan creates the real publisher, swap it for a FakePublisher
    so tests can assert on published events. We patch `nats_pub.NATSPublisher`
    class itself so the lifespan's `NATSPublisher(...)` call returns the fake.
    """
    import nats_pub as nats_pub_mod

    class FakePublisher:
        def __init__(self, *args, **kwargs):
            self.calls: List[Dict[str, Any]] = []

        async def connect(self):
            return True

        async def disconnect(self):
            return None

        @property
        def connected(self):
            return True

        async def publish(self, subject, payload):
            self.calls.append({"subject": subject, "payload": payload})
            return True

        async def publish_room_launched(self, **kwargs):
            self.calls.append({"subject": "p7.nats.launch", "payload": kwargs})
            return True

        async def publish_room_session(self, **kwargs):
            self.calls.append({"subject": "p7.nats.session", "payload": kwargs})
            return True

        async def publish_room_updated(self, **kwargs):
            self.calls.append({"subject": "room.session.updated.v1", "payload": kwargs})
            return True

        async def publish_config_reloaded(self, **kwargs):
            self.calls.append({"subject": "pmoves.config.rooms.reloaded.v1", "payload": kwargs})
            return True

    monkeypatch.setattr(nats_pub_mod, "NATSPublisher", FakePublisher)
    yield


@pytest.fixture
def client(hermetic_settings, catalog_with_two_rooms):
    """FastAPI TestClient with the hermetic pmoves root."""
    # Reload main module-level state so it picks up the env vars set by
    # hermetic_settings.
    import importlib
    import main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["rooms_loaded"] == 2
    assert body["schema_version"] == "1.2.0"


def test_list_rooms(client):
    r = client.get("/api/p7/rooms")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    room_ids = {row["room_id"] for row in body["rooms"]}
    assert "ready.room.test" in room_ids
    assert "notready.room.test" in room_ids


def test_get_room_detail(client):
    r = client.get("/api/p7/rooms/ready.room.test")
    assert r.status_code == 200
    body = r.json()
    assert body["catalog_row"]["room_id"] == "ready.room.test"
    assert body["manifest"] is not None
    assert body["manifest_error"] is None


def test_get_room_detail_not_found(client):
    r = client.get("/api/p7/rooms/does.not.exist")
    assert r.status_code == 404


def test_transition_rehearsal_to_live_succeeds(client):
    r = client.post(
        "/api/p7/rooms/ready.room.test/transition",
        json={"target_stage": "live", "reason": "test promotion", "requester": "tester"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["current_stage"] == "live"
    assert body["previous_stage"] == "rehearsal"
    assert body["noop"] is False


def test_transition_rehearsal_to_live_fails_checklist(client):
    r = client.post(
        "/api/p7/rooms/notready.room.test/transition",
        json={"target_stage": "live", "reason": "no card", "requester": "tester"},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "chit_checklist_failed"
    assert "unchecked" in body
    assert len(body["unchecked"]) > 0


def test_transition_invalid_target_stage(client):
    r = client.post(
        "/api/p7/rooms/ready.room.test/transition",
        json={"target_stage": "bogus", "reason": "x", "requester": "t"},
    )
    # 400 from TransitionError handler (raised in transition() before engine)
    assert r.status_code in (400, 422)


def test_transition_invalid_state_machine_path(client):
    # rehearsal → review is not valid (must go rehearsal → live → review)
    r = client.post(
        "/api/p7/rooms/ready.room.test/transition",
        json={"target_stage": "review", "reason": "skip live", "requester": "t"},
    )
    assert r.status_code == 409
    body = r.json()
    assert body["error"] == "invalid_transition"


def test_transition_missing_field_validation(client):
    # target_stage required
    r = client.post(
        "/api/p7/rooms/ready.room.test/transition",
        json={"reason": "x", "requester": "t"},
    )
    assert r.status_code == 422  # pydantic validation


def test_reload(client):
    r = client.post("/api/p7/reload")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "reloaded"
    assert body["rooms_loaded"] == 2
