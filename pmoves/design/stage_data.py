"""Bake the /stage/ rooms-on-a-stage A2UI surface from public room manifests.

Reads pmoves/config/rooms/catalog.json + manifests, filters to public rooms
(same rules as isPublicRoom() in pmoves/ui/lib/rooms.ts), and emits
website/stage/data/public-rooms.json as an A2UI ServerToClientMessage array.

The baked file is byte-for-byte a valid agent message stream: the same JSON an
agent could push over the A2UI NATS Bridge renders identically (DL-4 spec D2).
All values are literalString — no data model needed for a static bake.

Run via `make -C pmoves stage-data`; drift gate is `stage-data-check`.
"""

from __future__ import annotations

import argparse
import json
import pathlib

DESIGN = pathlib.Path(__file__).resolve().parent
ROOMS_DIR = DESIGN.parent / "config" / "rooms"
DEFAULT_OUT = DESIGN.parent.parent / "website" / "stage" / "data" / "public-rooms.json"

SURFACE_ID = "stage-rooms"


def is_public_room(manifest: dict) -> bool:
    """Mirror of isPublicRoom() in pmoves/ui/lib/rooms.ts.

    A room is public unless its manifest marks it private/unlisted, owner-only,
    or opts out of the public catalog. Keep the two implementations in sync —
    pmoves/ui/lib/__tests__/rooms.test.ts and tests/test_stage_data.py both pin
    the same expected public set against the real manifests.
    """
    access = manifest.get("access")
    if not access:
        return True
    if access.get("exclude_from_public_catalog") is True:
        return False
    if access.get("owner_only") is True:
        return False
    if access.get("visibility") in ("private", "unlisted"):
        return False
    return True


def load_public_rooms(rooms_dir: pathlib.Path = ROOMS_DIR) -> list[dict]:
    catalog = json.loads((rooms_dir / "catalog.json").read_text(encoding="utf-8-sig"))
    rooms = []
    for entry in catalog["rooms"]:
        manifest_path = rooms_dir / entry["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if manifest["room_id"] != entry["room_id"]:
            raise ValueError(
                f"{entry['manifest']}: manifest room_id {manifest['room_id']} != catalog {entry['room_id']}"
            )
        if is_public_room(manifest):
            rooms.append({"entry": entry, "manifest": manifest})
    rooms.sort(key=lambda room: room["manifest"]["display_name"])
    return rooms


def _text(component_id: str, text: str, usage_hint: str | None = None) -> dict:
    body: dict = {"text": {"literalString": text}}
    if usage_hint:
        body["usageHint"] = usage_hint
    return {"id": component_id, "component": {"Text": body}}


def _apps_line(manifest: dict) -> str:
    parts = []
    for app in manifest.get("apps", []):
        status = app.get("status", "active")
        label = app["app_id"] if status == "active" else f"{app['app_id']} ({status})"
        parts.append(label)
    return " · ".join(parts)


def _enter_button(prefix: str, room_id: str) -> tuple[dict, dict, str]:
    """Return (button_component, label_text_component, label_id) for the room's Enter button.

    The Button dispatches an `a2ui.action` with name="openroom.enter" and
    context containing the room_id. stage.js listens for the event and
    navigates to `${OPENROOM_BASE_URL}/?room=<room_id>`. OPENROOM_BASE_URL
    is set via <meta name="pmoves-openroom-base-url"> in index.html (default
    http://localhost:5173/webuiapps/ for local dev).
    """
    label_id = f"{prefix}_enter_label"
    return (
        {
            "id": f"{prefix}_enter",
            "component": {
                "Button": {
                    "child": label_id,
                    "primary": True,
                    "action": {
                        "name": "openroom.enter",
                        "context": [
                            {"key": "room_id", "value": {"literalString": room_id}}
                        ],
                    },
                }
            },
        },
        _text(label_id, "Enter →", "body"),
        label_id,
    )


def build_surface_messages(rooms: list[dict]) -> list[dict]:
    components: list[dict] = []
    card_ids: list[str] = []

    for index, room in enumerate(rooms):
        manifest = room["manifest"]
        room_id = manifest["room_id"]
        prefix = f"room{index}"
        glyph = (manifest.get("persona") or {}).get("glyph", "")
        title = f"{glyph} {manifest['display_name']}".strip()
        meta = f"{manifest.get('room_type', 'room')} · {manifest['agent_id']}"
        if manifest.get("alter"):
            meta += f" / {manifest['alter']}"

        child_ids = [f"{prefix}_title", f"{prefix}_meta"]
        components.append(_text(f"{prefix}_title", title, "h3"))
        components.append(_text(f"{prefix}_meta", meta, "caption"))

        description = manifest.get("description") or room["entry"].get("summary")
        if description:
            child_ids.append(f"{prefix}_desc")
            components.append(_text(f"{prefix}_desc", description))

        apps_line = _apps_line(manifest)
        if apps_line:
            child_ids.append(f"{prefix}_apps")
            components.append(_text(f"{prefix}_apps", f"Apps: {apps_line}", "caption"))

        # P3 (openroom-realization slice 2): Enter button to navigate to the
        # OpenRoom desktop with the room id as ?room= query param. Adapter
        # header comment in pmovesRoomAdapter documents the wiring.
        enter_button, enter_label, _ = _enter_button(prefix, room_id)
        child_ids.append(f"{prefix}_enter")
        components.append(enter_button)
        components.append(enter_label)

        components.append(
            {
                "id": f"{prefix}_column",
                "component": {
                    "Column": {
                        "children": {"explicitList": child_ids},
                        "alignment": "start",
                    }
                },
            }
        )
        components.append(
            {"id": f"{prefix}_card", "component": {"Card": {"child": f"{prefix}_column"}}}
        )
        card_ids.append(f"{prefix}_card")

    components.append(
        {
            "id": "stage_root",
            "component": {
                "Column": {
                    "children": {"explicitList": card_ids},
                    "alignment": "stretch",
                }
            },
        }
    )

    return [
        {"beginRendering": {"surfaceId": SURFACE_ID, "root": "stage_root"}},
        {"surfaceUpdate": {"surfaceId": SURFACE_ID, "components": components}},
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    messages = build_surface_messages(load_public_rooms())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(messages, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
