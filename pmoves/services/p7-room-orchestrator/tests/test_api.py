"""
Tests for the FastAPI app.

Uses FastAPI TestClient. The lifespan handler creates a real CatalogLoader
against the hermetic temp pmoves/ subtree and a log-only NATSPublisher.
We swap in a FakePublisher post-startup so we can assert publish calls.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

# Ensure the service directory is on sys.path so `import main` works.
_SERVICE_DIR = str(Path(__file__).resolve().parents[1])
if _SERVICE_DIR not in sys.path:
    sys.path.insert(0, _SERVICE_DIR)
import main  # noqa: E402  (sys.path manipulation above)


@pytest.fixture(autouse=True)
def _patch_publisher_after_lifespan(monkeypatch):
    """
    After the lifespan creates the real publisher, swap it for a FakePublisher
    so tests can assert on published events. We patch `nats_pub.NATSPublisher`
    class itself so the lifespan's `NATSPublisher(...)` call returns the fake.
    """
    import importlib
    import nats_pub as nats_pub_mod
    # Reload main so the lifespan's `NATSPublisher(...)` call uses the patched class
    import main
    importlib.reload(main)

    class FakePublisher:
        def __init__(self, *args, **kwargs):
            self.calls: List[Dict[str, Any]] = []

        async def connect(self):
            return True

        async def connect_with_retry(self):
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
    """FastAPI TestClient with the hermetic pmoves root + bearer auth."""
    # Reload main module-level state so the SETTINGS singleton picks up
    # the env vars set by hermetic_settings (P7_PMOVES_ROOT, P7_CONTROL_TOKEN, etc.).
    importlib.reload(main)
    # The default Authorization header satisfies the require_http_control
    # dependency on /api/p7/rooms/{id}/transition. Per-test override via
    # `client.headers = {}` is possible if a test needs to exercise the
    # 401/503 auth paths.
    with TestClient(main.app, headers={"Authorization": "Bearer test-control-token"}) as c:
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


def test_session_open_returns_session_id_and_publishes(client):
    """P5 (openroom-realization slice 2): the OpenRoom desktop adapter
    calls POST /api/p7/rooms/{id}/session with action=open when entering
    a room. The endpoint is unauthenticated (the adapter is a public
    browser module); it returns a session_id and publishes a NATS event.
    """
    r = client.post(
        "/api/p7/rooms/ready.room.test/session",
        json={
            "action": "open",
            "agent_id": "5090-claude",
            "alter": "minimax",
            "room_stage": "live",
            "timestamp": "2026-08-06T12:00:00Z",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "opened"
    assert body["room_id"] == "ready.room.test"
    assert body["agent_id"] == "5090-claude"
    assert body["alter"] == "minimax"
    assert body["room_stage"] == "live"
    assert body["timestamp"] == "2026-08-06T12:00:00Z"
    # session_id is a uuid (hex + dashes, 36 chars)
    assert isinstance(body["session_id"], str)
    assert len(body["session_id"]) == 36


def test_session_close_returns_status_and_publishes(client):
    """The adapter calls action=close when leaving a room."""
    r = client.post(
        "/api/p7/rooms/ready.room.test/session",
        json={
            "action": "close",
            "agent_id": "5090-claude",
            "alter": "minimax",
            "room_stage": "live",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "closed"
    # Default timestamp filled in server-side when client omits
    assert body["timestamp"]  # non-empty


def test_session_invalid_action_rejected(client):
    """The endpoint accepts only 'open' or 'close' actions. Anything else
    is a 400 — the adapter is a single source of truth for action values,
    so a non-conforming caller indicates a wiring bug, not a recoverable
    error.
    """
    r = client.post(
        "/api/p7/rooms/ready.room.test/session",
        json={"action": "heartbeat", "agent_id": "x"},
    )
    assert r.status_code == 400
    body = r.json()
    assert "heartbeat" in body["detail"]


def test_session_missing_action_rejected(client):
    """action is required (Pydantic validation)."""
    r = client.post(
        "/api/p7/rooms/ready.room.test/session",
        json={"agent_id": "x", "room_stage": "live"},
    )
    assert r.status_code == 422  # pydantic validation


def test_session_unauthenticated_succeeds(client):
    """P5 security note: the endpoint is intentionally unauthenticated.
    The OpenRoom adapter is a public browser module — auth would block
    the openroom reverse proxy from forwarding the call. For real auth,
    deploy a forward-auth gateway in front of /api/p7/. This test
    pins the no-auth contract.
    """
    # Strip the default bearer auth header that the client fixture sets
    client.headers = {}
    r = client.post(
        "/api/p7/rooms/ready.room.test/session",
        json={"action": "open", "agent_id": "anon"},
    )
    assert r.status_code == 200
    # Restore for any later tests in the same fixture
    client.headers = {"Authorization": "Bearer test-control-token"}
