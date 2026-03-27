#!/usr/bin/env python3
"""Validate PMOVES room manifest seeds against the room schema and catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

try:
    import jsonschema
except ModuleNotFoundError as exc:  # pragma: no cover - dependency should exist in PMOVES envs
    raise SystemExit("jsonschema is required to validate room manifests") from exc

try:
    from referencing import Registry, Resource
except ModuleNotFoundError:  # pragma: no cover - fallback for older envs
    Registry = None
    Resource = None

SCRIPT_DIR = Path(__file__).resolve().parent
PMOVES_ROOT = SCRIPT_DIR.parent
ROOM_DIR = PMOVES_ROOT / "config" / "rooms"
SCHEMA_DIR = PMOVES_ROOT / "contracts" / "schemas" / "room"
CATALOG_PATH = ROOM_DIR / "catalog.json"
ROOM_SCHEMA_PATH = SCHEMA_DIR / "room.manifest.v1.schema.json"
SKILL_SCHEMA_PATH = SCHEMA_DIR / "skill.binding.v1.schema.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_validator() -> jsonschema.Draft202012Validator:
    room_schema = read_json(ROOM_SCHEMA_PATH)
    skill_schema = read_json(SKILL_SCHEMA_PATH)

    room_schema.setdefault("$id", ROOM_SCHEMA_PATH.resolve().as_uri())
    skill_schema.setdefault("$id", SKILL_SCHEMA_PATH.resolve().as_uri())

    if Registry is not None and Resource is not None:
        registry = Registry().with_resources(
            [
                (room_schema["$id"], Resource.from_contents(room_schema)),
                (skill_schema["$id"], Resource.from_contents(skill_schema)),
            ]
        )
        return jsonschema.Draft202012Validator(room_schema, registry=registry)

    resolver = jsonschema.RefResolver(base_uri=room_schema["$id"], referrer=room_schema)
    return jsonschema.Draft202012Validator(room_schema, resolver=resolver)


def iter_catalog_entries(catalog: dict, only_room_id: str | None) -> Iterable[dict]:
    rooms = catalog.get("rooms", [])
    for entry in rooms:
        if only_room_id and entry.get("room_id") != only_room_id:
            continue
        yield entry


def validate_entry(entry: dict, validator: jsonschema.Draft202012Validator) -> tuple[Path, dict]:
    manifest_name = entry.get("manifest")
    if not manifest_name:
        raise ValueError(f"catalog entry {entry.get('room_id', '<unknown>')} is missing 'manifest'")

    manifest_path = ROOM_DIR / manifest_name
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    manifest = read_json(manifest_path)
    validator.validate(manifest)

    for key in ("room_id", "agent_id", "alter", "display_name"):
        catalog_value = entry.get(key)
        manifest_value = manifest.get(key)
        if catalog_value is not None and manifest_value != catalog_value:
            raise ValueError(
                f"catalog mismatch for {manifest_name}: {key}={manifest_value!r} != {catalog_value!r}"
            )

    return manifest_path, manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--room-id", help="Validate a single room_id from the catalog")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-room summary output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    catalog = read_json(CATALOG_PATH)
    validator = build_validator()
    matched = list(iter_catalog_entries(catalog, args.room_id))

    if not matched:
        raise SystemExit(f"No catalog entries found for room_id={args.room_id!r}")

    seen_ids: set[str] = set()
    for entry in matched:
        manifest_path, manifest = validate_entry(entry, validator)
        room_id = manifest["room_id"]
        if room_id in seen_ids:
            raise ValueError(f"duplicate room_id in selection: {room_id}")
        seen_ids.add(room_id)

        if not args.quiet:
            apps = len(manifest.get("apps", []))
            skills = len(manifest.get("skill_bindings", []))
            route = manifest.get("shell", {}).get("layout", {}).get("default_route", "-")
            print(f"OK {manifest_path.name} room_id={room_id} apps={apps} skills={skills} route={route}")

    if args.quiet:
        print(f"validated {len(matched)} room manifest(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())