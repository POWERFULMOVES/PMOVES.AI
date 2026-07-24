"""Bake the /stage/ rooms-on-a-stage A2UI surface from public room manifests.

Reads pmoves/config/rooms/catalog.json + manifests, filters to public rooms
(same rules as isPublicRoom() in pmoves/ui/lib/rooms.ts), and emits
website/stage/data/public-rooms.json as an A2UI ServerToClientMessage array.

The baked file is byte-for-byte a valid agent message stream: the same JSON an
agent could push over the A2UI NATS Bridge renders identically (DL-4 spec D2).
All values are literalString — no data model needed for a static bake.

Each public room card gets an Enter button (added 2026-07-24 as part of the
openroom-adapter lane, see pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md). The
button's action is {name: "enter-room", context: [{key: "room_id", ...}]} —
website/stage/stage.js attaches a global click listener that intercepts this
action and navigates to OPENROOM_BASE_URL?room=<id> (or, in local dev,
http://localhost:5173/?room=<id>).

Run via `make -C pmoves stage-data`; drift gate is `stage-data-check`.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib

DESIGN = pathlib.Path(__file__).resolve().parent
ROOMS_DIR = DESIGN.parent / "config" / "rooms"
DEFAULT_OUT = DESIGN.parent.parent / "website" / "stage" / "data" / "public-rooms.json"

SURFACE_ID = "stage-rooms"

# Where the Enter button navigates. Override via OPENROOM_BASE_URL env var
# (e.g. http://localhost:5173 for local vite dev, https://openroom.pmoves.ai
# for prod, http://staging.openroom.pmoves.ai for staging). The action carries
# the room_id; stage.js reads OPENROOM_BASE_URL at runtime if available.
OPENROOM_BASE_URL_DEFAULT = "https://openroom.pmoves.ai"


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


def _enter_button(prefix: str, room_id: str, base_url: str) -> list[dict]:
    """Emit the 'Enter' button + child Text for a room card.

    The action's context carries both the room_id and the full navigation URL
    (resolved at bake time from OPENROOM_BASE_URL). stage.js attaches a global
    click listener that intercepts this action and navigates to the URL.
    Keeping the URL in the bake means operators can re-point at staging/local
    by re-running `make stage-data OPENROOM_BASE_URL=...` without touching
    stage.js.
    """
    text_id = f"{prefix}_enter_text"
    button_id = f"{prefix}_enter_button"
    target_url = f"{base_url.rstrip('/')}/?room={room_id}"
    return [
        _text(text_id, "Enter \u2192", "body"),
        {
            "id": button_id,
            "component": {
                "Button": {
                    "child": text_id,
                    "primary": True,
                    "action": {
                        "name": "enter-room",
                        "context": [
                            {"key": "room_id", "value": {"literalString": room_id}},
                            {"key": "url", "value": {"literalString": target_url}},
                        ],
                    },
                }
            },
        },
    ]


def _apps_line(manifest: dict) -> str:
    parts = []
    for app in manifest.get("apps", []):
        status = app.get("status", "active")
        label = app["app_id"] if status == "active" else f"{app['app_id']} ({status})"
        parts.append(label)
    return " · ".join(parts)


def build_surface_messages(rooms: list[dict]) -> list[dict]:
    components: list[dict] = []
    card_ids: list[str] = []

    for index, room in enumerate(rooms):
        manifest = room["manifest"]
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

        # Enter button (openroom-adapter lane, 2026-07-24). Always last child
        # so the card lays out title/meta/desc/apps above the action.
        base_url = os.environ.get("OPENROOM_BASE_URL", OPENROOM_BASE_URL_DEFAULT)
        button_components = _enter_button(prefix, manifest["room_id"], base_url)
        for c in button_components:
            components.append(c)
            child_ids.append(c["id"])

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
