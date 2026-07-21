# pmoves/design/tests/test_stage_data.py
import json
import pathlib
import sys

DESIGN = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESIGN))

from stage_data import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    SURFACE_ID,
    build_surface_messages,
    is_public_room,
    load_public_rooms,
)


def test_is_public_room_mirrors_rooms_ts_rules():
    assert is_public_room({}) is True
    assert is_public_room({"access": {}}) is True
    assert is_public_room({"access": {"visibility": "public"}}) is True
    assert is_public_room({"access": {"visibility": "private"}}) is False
    assert is_public_room({"access": {"visibility": "unlisted"}}) is False
    assert is_public_room({"access": {"owner_only": True}}) is False
    assert is_public_room({"access": {"exclude_from_public_catalog": True}}) is False


def test_load_public_rooms_curates_real_manifests():
    room_ids = {room["manifest"]["room_id"] for room in load_public_rooms()}
    assert "tokenism.room.exchange" in room_ids
    # Control/infra/persona rooms must never leak onto the public stage.
    assert "darkxsides.room" not in room_ids
    assert not any(rid.startswith(("4090-", "z890-", "hermes-", "5090-")) for rid in room_ids)


def test_messages_are_a_valid_static_surface():
    rooms = load_public_rooms()
    messages = build_surface_messages(rooms)

    begin = messages[0]["beginRendering"]
    assert begin["surfaceId"] == SURFACE_ID

    components = messages[1]["surfaceUpdate"]["components"]
    assert messages[1]["surfaceUpdate"]["surfaceId"] == SURFACE_ID
    by_id = {component["id"]: component["component"] for component in components}
    assert begin["root"] in by_id

    # Every child reference must resolve — a dangling id renders a blank card.
    for component in by_id.values():
        for spec in component.values():
            for child in spec.get("children", {}).get("explicitList", []):
                assert child in by_id, f"dangling child ref {child}"
            if "child" in spec:
                assert spec["child"] in by_id

    # Static bake means literals only: a path binding without a dataModelUpdate
    # would render "(no model)".
    texts = [
        spec["text"]["literalString"]
        for component in by_id.values()
        for name, spec in component.items()
        if name == "Text"
    ]
    for room in rooms:
        assert any(room["manifest"]["display_name"] in text for text in texts)


def test_planned_apps_are_labeled_not_hidden():
    messages = build_surface_messages(load_public_rooms())
    blob = json.dumps(messages)
    # Manifest-honesty rule, both directions: planned apps carry the label
    # (Fordham's ballot-box until it's wired as a room app)...
    assert "ballot-box (planned)" in blob
    # ...and wealth-ledger DROPPED the label when W2 landed the wiring
    # (G1 export live-verified 2026-07-20: 52wk/156tx dry-run + NATS event
    # on the fleet broker).
    assert "wealth-ledger (planned)" not in blob
    assert "wealth-ledger" in blob


def test_output_is_deterministic():
    rooms = load_public_rooms()
    first = json.dumps(build_surface_messages(rooms), indent=2)
    second = json.dumps(build_surface_messages(load_public_rooms()), indent=2)
    assert first == second
