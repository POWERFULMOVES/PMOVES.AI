from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import time
from datetime import datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from jsonschema import ValidationError


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
SPEC = importlib.util.spec_from_file_location("p7_room_orchestrator", APP_PATH)
assert SPEC and SPEC.loader
p7 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p7)


@pytest.fixture(autouse=True)
def clear_sessions() -> None:
    p7._sessions.clear()
    p7._room_stages.clear()
    p7._room_locks.clear()
    p7._used_activation_nonces.clear()


def test_catalog_entry_resolves_full_manifest() -> None:
    manifest = p7.get_room_manifest("4090-field.room.control")

    assert manifest["room_id"] == "4090-field.room.control"
    assert manifest["stage"] == "rehearsal"
    assert len(manifest["apps"]) == 5
    assert "manifest" not in manifest


def test_manifest_path_cannot_escape_room_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    room_dir = tmp_path / "rooms"
    room_dir.mkdir()
    (tmp_path / "outside.json").write_text("{}", encoding="utf-8")
    (room_dir / "catalog.json").write_text(
        json.dumps({"rooms": [{"room_id": "unsafe.room", "manifest": "../outside.json"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(p7, "ROOM_CATALOG_PATH", room_dir / "catalog.json")

    with pytest.raises(HTTPException, match="Unsafe manifest path") as exc:
        p7.get_room_manifest("unsafe.room")

    assert exc.value.status_code == 500


def test_room_stage_and_session_state_are_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    published: list[tuple[str, dict]] = []

    async def fake_record(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    async def fake_publish(subject: str, payload: dict, **kwargs) -> None:  # noqa: ANN003
        published.append((subject, payload))

    monkeypatch.setattr(p7, "record_session", fake_record)
    monkeypatch.setattr(p7.publisher, "publish", fake_publish)
    monkeypatch.setattr(type(p7.publisher), "connected", property(lambda self: True))
    monkeypatch.setattr(p7, "validate_chit", lambda *args: "00000000-0000-4000-8000-000000000001")

    session = asyncio.run(
        p7.transition_session("4090-field.room.control", p7.SessionState.ACTIVE)
    )
    assert session.state == p7.SessionState.ACTIVE
    assert session.stage == p7.RoomStage.REHEARSAL

    session = asyncio.run(
        p7.transition_stage("4090-field.room.control", p7.RoomStage.LIVE)
    )
    assert session.state == p7.SessionState.ACTIVE
    assert session.stage == p7.RoomStage.LIVE
    assert any(subject == p7.NATS_SUBJECT_STAGE for subject, _ in published)


def test_live_stage_requires_active_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(p7, "validate_chit", lambda *args: "00000000-0000-4000-8000-000000000001")

    with pytest.raises(HTTPException, match="session must be active") as exc:
        asyncio.run(p7.transition_stage("4090-field.room.control", p7.RoomStage.LIVE))

    assert exc.value.status_code == 409


def test_live_stage_requires_nats_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_record(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    async def fake_publish(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    monkeypatch.setattr(p7, "record_session", fake_record)
    monkeypatch.setattr(p7.publisher, "publish", fake_publish)
    monkeypatch.setattr(p7, "validate_chit", lambda *args: "00000000-0000-4000-8000-000000000001")

    asyncio.run(p7.transition_session("4090-field.room.control", p7.SessionState.ACTIVE))
    with pytest.raises(HTTPException, match="NATS stage-fact delivery required") as exc:
        asyncio.run(p7.transition_stage("4090-field.room.control", p7.RoomStage.LIVE))

    assert exc.value.status_code == 503
    assert p7._sessions["4090-field.room.control"].stage == p7.RoomStage.REHEARSAL


def test_room_archive_requires_ended_session(monkeypatch: pytest.MonkeyPatch) -> None:
    session = p7.get_or_create_session("4090-field.room.control")
    session.stage = p7.RoomStage.REVIEW
    session.state = p7.SessionState.ACTIVE

    with pytest.raises(HTTPException, match="session must be ended") as exc:
        asyncio.run(p7.transition_stage("4090-field.room.control", p7.RoomStage.ARCHIVE))

    assert exc.value.status_code == 409


def test_stage_publish_failure_rolls_back_durable_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[tuple[str, str]] = []

    async def fake_record(session, action: str, **kwargs) -> None:  # noqa: ANN001, ANN003
        recorded.append((action, session.stage.value))

    async def fake_publish(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
        raise HTTPException(status_code=502, detail="publish failed")

    monkeypatch.setattr(p7, "record_session", fake_record)
    monkeypatch.setattr(p7.publisher, "publish", fake_publish)
    monkeypatch.setattr(type(p7.publisher), "connected", property(lambda self: True))
    monkeypatch.setattr(p7, "validate_chit", lambda *args: "00000000-0000-4000-8000-000000000001")

    session = p7.get_or_create_session("4090-field.room.control")
    session.state = p7.SessionState.ACTIVE

    with pytest.raises(HTTPException, match="publish failed"):
        asyncio.run(p7.transition_stage("4090-field.room.control", p7.RoomStage.LIVE))

    assert session.stage == p7.RoomStage.REHEARSAL
    assert recorded == [
        ("stage:rehearsal->live", "live"),
        ("stage-rollback:live->rehearsal", "rehearsal"),
    ]
    assert session.checkpoints[-2]["stage"] == "live"
    assert session.checkpoints[-1]["rollback"] is True
    assert session.checkpoints[-1]["failed_stage"] == "live"
    assert session.checkpoints[-1]["signing_card_id"] == "00000000-0000-4000-8000-000000000001"


def test_chit_uses_active_signing_card_for_room_owner() -> None:
    manifest = p7.get_room_manifest("4090-field.room.control")

    assert p7._resolve_signing_card(manifest)["card_id"] == "00000000-0000-4000-8000-000000000012"


def test_chit_fails_when_room_owner_has_no_signing_card() -> None:
    manifest = p7.get_room_manifest("5090-kilocode.room.studio")

    with pytest.raises(HTTPException, match="no active signing card") as exc:
        p7._resolve_signing_card(manifest)

    assert exc.value.status_code == 422


def test_live_audit_persistence_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    session = p7.RoomSession(
        "4090-field.room.control",
        p7.get_room_manifest("4090-field.room.control"),
    )
    session.state = p7.SessionState.ACTIVE
    session.started_at = 1.0
    monkeypatch.setattr(p7, "SUPABASE_REST_URL", "")
    monkeypatch.setattr(p7, "SUPABASE_KEY", "")

    with pytest.raises(HTTPException, match="audit persistence required") as exc:
        asyncio.run(p7.record_session(session, "stage:rehearsal->live", required=True))

    assert exc.value.status_code == 503


def test_supabase_timestamps_are_iso_8601() -> None:
    serialized = p7._iso_timestamp(1.0)

    assert serialized is not None
    parsed = datetime.fromisoformat(serialized)
    assert parsed.tzinfo is not None
    assert parsed.timestamp() == 1.0


def test_supabase_write_targets_pmoves_core_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):  # noqa: ANN204
            return self

        async def __aexit__(self, *args) -> None:  # noqa: ANN002
            return None

        async def post(self, url: str, *, json: dict, headers: dict) -> FakeResponse:
            captured.update({"url": url, "json": json, "headers": headers})
            return FakeResponse()

    session = p7.RoomSession(
        "4090-field.room.control",
        p7.get_room_manifest("4090-field.room.control"),
    )
    session.state = p7.SessionState.ACTIVE
    session.started_at = 1.0
    monkeypatch.setattr(p7, "SUPABASE_REST_URL", "http://supabase.test/rest/v1")
    monkeypatch.setattr(p7, "SUPABASE_KEY", "test-key")
    monkeypatch.setattr(p7, "SUPABASE_SCHEMA", "pmoves_core")
    monkeypatch.setattr(p7.httpx, "AsyncClient", FakeClient)

    asyncio.run(p7.record_session(session, "session:planned->active"))

    assert captured["headers"]["Content-Profile"] == "pmoves_core"
    assert captured["headers"]["Accept-Profile"] == "pmoves_core"
    assert captured["url"].startswith("http://supabase.test/rest/v1/room_sessions")
    assert captured["json"]["started_at"].endswith("+00:00")
    assert captured["json"]["metadata"]["history"] == []


def test_live_checkpoint_preserves_signing_card_in_audit_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []

    async def fake_record(session, action: str, **kwargs) -> None:  # noqa: ANN001, ANN003
        captured.append(
            {
                "action": action,
                "required": kwargs.get("required", False),
                "history": [dict(item) for item in session.checkpoints],
            }
        )

    async def fake_publish(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    monkeypatch.setattr(p7, "record_session", fake_record)
    monkeypatch.setattr(p7.publisher, "publish", fake_publish)
    monkeypatch.setattr(type(p7.publisher), "connected", property(lambda self: True))
    monkeypatch.setattr(p7, "validate_chit", lambda *args: "00000000-0000-4000-8000-000000000001")

    session = asyncio.run(
        p7.transition_session("4090-field.room.control", p7.SessionState.ACTIVE)
    )
    session = asyncio.run(
        p7.transition_stage("4090-field.room.control", p7.RoomStage.LIVE)
    )

    assert session.stage == p7.RoomStage.LIVE
    assert captured[-1]["required"] is True
    assert captured[-1]["history"][-1]["previous_stage"] == "rehearsal"
    assert captured[-1]["history"][-1]["stage"] == "live"
    assert captured[-1]["history"][-1]["signing_card_id"] == "00000000-0000-4000-8000-000000000001"


def test_command_and_fact_subjects_are_distinct() -> None:
    commands = {
        p7.NATS_COMMAND_LAUNCH,
        p7.NATS_COMMAND_LAUNCH_V1,
        p7.NATS_COMMAND_SESSION,
        p7.NATS_COMMAND_SESSION_V1,
    }
    facts = {
        p7.NATS_SUBJECT_STARTED,
        p7.NATS_SUBJECT_CHECKPOINT,
        p7.NATS_SUBJECT_ENDED,
        p7.NATS_SUBJECT_STAGE,
        p7.NATS_SUBJECT_FAILED,
    }

    assert commands.isdisjoint(facts)


def test_stage_hydration_seeds_new_session_from_latest_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict]:
            return [{"metadata": {"stage": "review"}}]

    class FakeClient:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            return None

        async def __aenter__(self):  # noqa: ANN204
            return self

        async def __aexit__(self, *args) -> None:  # noqa: ANN002
            return None

        async def get(self, *args, **kwargs) -> FakeResponse:  # noqa: ANN002, ANN003
            return FakeResponse()

    monkeypatch.setattr(p7, "SUPABASE_REST_URL", "http://supabase.test/rest/v1")
    monkeypatch.setattr(p7, "SUPABASE_KEY", "test-key")
    monkeypatch.setattr(p7.httpx, "AsyncClient", FakeClient)

    asyncio.run(p7.hydrate_room_stages())
    session = p7.get_or_create_session("4090-field.room.control")

    assert session.stage == p7.RoomStage.REVIEW
    assert session.state == p7.SessionState.PLANNED


def test_concurrent_session_transitions_are_serialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_record(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
        await asyncio.sleep(0)

    async def fake_publish(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
        await asyncio.sleep(0)

    async def run_transitions() -> list[object]:
        return await asyncio.gather(
            p7.transition_session("4090-field.room.control", p7.SessionState.ACTIVE),
            p7.transition_session("4090-field.room.control", p7.SessionState.ACTIVE),
            return_exceptions=True,
        )

    monkeypatch.setattr(p7, "record_session", fake_record)
    monkeypatch.setattr(p7.publisher, "publish", fake_publish)

    results = asyncio.run(run_transitions())

    assert sum(isinstance(result, p7.RoomSession) for result in results) == 1
    conflicts = [result for result in results if isinstance(result, HTTPException)]
    assert len(conflicts) == 1
    assert conflicts[0].status_code == 409


def test_versioned_pbnj_session_action_maps_to_p7_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, p7.SessionState]] = []

    class FakeMessage:
        data = json.dumps(
            {
                "room": "5090-voice.room.studio",
                "action": "stopped",
            }
        ).encode()

    async def fake_transition(room_id: str, target: p7.SessionState, **kwargs) -> None:  # noqa: ANN003
        captured.append((room_id, target))

    monkeypatch.setattr(p7, "transition_session", fake_transition)

    asyncio.run(p7.publisher._handle_session(FakeMessage()))

    assert captured == [("5090-voice.room.studio", p7.SessionState.ENDED)]


def test_versioned_pbnj_launch_action_maps_to_p7_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, p7.SessionState]] = []

    class FakeMessage:
        data = json.dumps(
            {
                "room": "5090-voice.room.studio",
                "app": "flute-gateway",
                "action": "started",
            }
        ).encode()

    async def fake_transition(room_id: str, target: p7.SessionState, **kwargs) -> None:  # noqa: ANN003
        captured.append((room_id, target))

    monkeypatch.setattr(p7, "transition_session", fake_transition)

    asyncio.run(p7.publisher._handle_launch(FakeMessage()))

    assert captured == [("5090-voice.room.studio", p7.SessionState.ACTIVE)]


def test_live_activation_requires_locally_verifiable_card_material() -> None:
    manifest = p7.get_room_manifest("4090-field.room.control")
    proof = p7.ActivationProof(
        card_id="00000000-0000-4000-8000-000000000012",
        nonce="nonce-with-16-chars",
        issued_at=int(time.time()),
        signature="not-a-real-signature",
    )

    with pytest.raises(HTTPException, match="no locally verifiable SSH key material") as exc:
        p7.validate_chit(manifest, proof, b"activation")

    assert exc.value.status_code == 422


def test_live_activation_verifies_nonce_bound_ed25519_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    ).decode()
    card_id = "00000000-0000-4000-8000-000000000001"
    card = {
        "card_id": card_id,
        "ml": {
            "primary_method": "ssh",
            "ssh_allowed_signers_line": f"darkxside {public_key} pmoves@pmoves.ai",
        },
    }
    monkeypatch.setattr(p7, "_resolve_signing_card", lambda manifest: card)
    proof = p7.ActivationProof(
        card_id=card_id,
        nonce="fresh-random-nonce-0001",
        issued_at=int(time.time()),
        signature="placeholder-value",
    )
    message = p7._activation_message(
        "test.room",
        "00000000-0000-4000-8000-000000000099",
        p7.RoomStage.REHEARSAL,
        p7.RoomStage.LIVE,
        proof,
    )
    proof = proof.model_copy(
        update={"signature": base64.b64encode(private_key.sign(message)).decode()}
    )

    assert p7.validate_chit({}, proof, message) == card_id
    with pytest.raises(HTTPException, match="nonce already used") as exc:
        p7.validate_chit({}, proof, message)
    assert exc.value.status_code == 409


def test_hydration_failure_refuses_git_seed_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingClient:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            return None

        async def __aenter__(self):  # noqa: ANN204
            return self

        async def __aexit__(self, *args) -> None:  # noqa: ANN002
            return None

        async def get(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(p7, "SUPABASE_REST_URL", "http://supabase.test/rest/v1")
    monkeypatch.setattr(p7, "SUPABASE_KEY", "test-key")
    monkeypatch.setattr(p7, "HYDRATION_ATTEMPTS", 1)
    monkeypatch.setattr(p7.httpx, "AsyncClient", FailingClient)

    with pytest.raises(RuntimeError, match="refusing Git-seed fallback"):
        asyncio.run(p7.hydrate_room_stages())


def test_explicit_start_rolls_over_ended_session(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_op(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    monkeypatch.setattr(p7, "record_session", no_op)
    monkeypatch.setattr(p7.publisher, "publish", no_op)
    old_session = p7.get_or_create_session("4090-field.room.control")
    old_session.state = p7.SessionState.ENDED
    old_id = old_session.session_id

    new_session = asyncio.run(
        p7.transition_session(
            "4090-field.room.control",
            p7.SessionState.ACTIVE,
            rollover=True,
        )
    )

    assert new_session.session_id != old_id
    assert new_session.state == p7.SessionState.ACTIVE


def test_archived_room_rejects_new_session() -> None:
    p7._room_stages["4090-field.room.control"] = p7.RoomStage.ARCHIVE

    with pytest.raises(HTTPException, match="Archived room cannot start") as exc:
        asyncio.run(
            p7.transition_session(
                "4090-field.room.control",
                p7.SessionState.ACTIVE,
                rollover=True,
            )
        )

    assert exc.value.status_code == 409


def test_unknown_launch_action_emits_failed_fact(monkeypatch: pytest.MonkeyPatch) -> None:
    published: list[tuple[str, dict]] = []
    transitioned: list[str] = []

    class FakeMessage:
        data = json.dumps({"room": "4090-field.room.control", "action": "strat"}).encode()

    async def fake_publish(subject: str, payload: dict, **kwargs) -> None:  # noqa: ANN003
        published.append((subject, payload))

    async def fake_transition(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
        transitioned.append("called")

    monkeypatch.setattr(p7.publisher, "publish", fake_publish)
    monkeypatch.setattr(p7, "transition_session", fake_transition)

    asyncio.run(p7.publisher._handle_launch(FakeMessage()))

    assert transitioned == []
    assert published[0][0] == p7.NATS_SUBJECT_FAILED


def test_p7_fact_schema_rejects_incomplete_payload() -> None:
    session = p7.get_or_create_session("4090-field.room.control")

    assert p7.validate_payload(p7.NATS_SUBJECT_CHECKPOINT, session.to_dict())
    with pytest.raises(ValidationError):
        p7.validate_payload(p7.NATS_SUBJECT_CHECKPOINT, {"room_id": session.room_id})


def test_http_control_authentication_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(p7, "P7_CONTROL_TOKEN", "control-secret")

    assert p7.require_http_control("Bearer control-secret") is None
    with pytest.raises(HTTPException, match="Invalid P7 HTTP control credentials") as exc:
        p7.require_http_control("Bearer wrong")
    assert exc.value.status_code == 401


def test_openroom_session_endpoint_open_close_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenRoom adapter lane (2026-07-24): POST /api/p7/rooms/{id}/session.

    action=open binds a session, returns session_id, and emits a NATS command
    on p7.nats.session. action=close ends the session and emits the matching
    close command. Both calls must be authorized by the bearer token.
    """
    from fastapi.testclient import TestClient

    monkeypatch.setattr(p7, "P7_CONTROL_TOKEN", "control-secret")
    captured: list[tuple[str, dict]] = []

    async def fake_publish(subject, payload, **kwargs):
        # Exercise the real schema validation that the production
        # publisher runs via envelope() -> validate_payload(). This way
        # a payload that fails the schema (e.g. `room_stage: null` on
        # close, which the p7.session.command.v1 schema rejects) makes
        # the test fail instead of silently passing. Only the NATS I/O
        # is stubbed out, not the validation layer.
        from pmoves.services.common.events import validate_payload

        validate_payload(subject, payload)
        captured.append((subject, payload))
        return None

    monkeypatch.setattr(p7.publisher, "publish", fake_publish)

    client = TestClient(p7.app)
    headers = {"Authorization": "Bearer control-secret"}

    # action=open
    res = client.post(
        "/api/p7/rooms/4090-field.room.control/session",
        json={
            "action": "open",
            "agent_id": "DARKXSIDE",
            "alter": "4090-demo",
            "room_stage": "rehearsal",
        },
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["action"] == "open"
    assert body["room_id"] == "4090-field.room.control"
    assert body["subject"] == "p7.nats.session.v1"
    session_id = body["session_id"]
    assert session_id
    open_capture = [c for c in captured if c[0] == "p7.nats.session.v1"]
    assert len(open_capture) == 1
    assert open_capture[0][1]["action"] == "open"
    assert open_capture[0][1]["session_id"] == session_id
    assert open_capture[0][1]["agent_id"] == "DARKXSIDE"

    # action=close
    res = client.post(
        "/api/p7/rooms/4090-field.room.control/session",
        json={
            "action": "close",
            "agent_id": "DARKXSIDE",
            "session_id": session_id,
        },
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["action"] == "close"
    # Filter to just our session commands (skip the STARTED/ENDED/CHECKPOINT
    # events emitted by the underlying state machine). Verify at least one
    # close command was published.
    close_captures = [c for c in captured if c[0] == "p7.nats.session.v1" and c[1].get("action") == "close"]
    assert len(close_captures) >= 1
    assert close_captures[0][1]["session_id"] == session_id

    # No bearer = 401
    res = client.post(
        "/api/p7/rooms/4090-field.room.control/session",
        json={"action": "open", "agent_id": "DARKXSIDE"},
    )
    assert res.status_code == 401

    # Bad action = 400
    res = client.post(
        "/api/p7/rooms/4090-field.room.control/session",
        json={"action": "rotate", "agent_id": "DARKXSIDE"},
        headers=headers,
    )
    assert res.status_code == 400

    # Re-entry after a close should NOT 409 (regression for the chatgpt-codex
    # P1: the OpenRoom adapter may enter/leave/enter the same room; the
    # ENDED -> ACTIVE transition needs rollover=True).
    res_open2 = client.post(
        "/api/p7/rooms/4090-field.room.control/session",
        json={"action": "open", "agent_id": "DARKXSIDE"},
        headers=headers,
    )
    assert res_open2.status_code == 200
    body_open2 = res_open2.json()
    assert body_open2["action"] == "open"
