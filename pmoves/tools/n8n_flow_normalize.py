#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any


def _as_workflow_obj(data: Any) -> dict[str, Any]:
    """
    Normalize various n8n export shapes into a minimal, importable workflow array format:
      - legacy stub shape (dict with keys: id=name, workflowId, nodes, connections, ...)
      - n8n CLI export shape (list with full metadata)
      - already-normalized shape (list with minimal keys)
    """
    if isinstance(data, list):
        if not data:
            raise ValueError("Empty workflow list")
        src = data[0]
    elif isinstance(data, dict):
        src = data
    else:
        raise TypeError(f"Unsupported JSON type: {type(data)}")

    # Legacy stub: "id" is the human name, "workflowId" may exist as an internal id.
    if isinstance(src, dict) and "nodes" in src and "connections" in src and "id" in src and "name" not in src:
        name = src.get("id") or "Unnamed workflow"
        settings = src.get("settings") or {}
        meta = src.get("meta") or {}
        return {
            "name": name,
            "nodes": src.get("nodes") or [],
            "connections": src.get("connections") or {},
            "settings": settings,
            "staticData": src.get("staticData"),
            # Import stub flows as inactive; activation is a separate step.
            "active": False,
            "meta": meta,
            "pinData": None,
            "versionId": str(uuid.uuid4()),
            "versionCounter": 1,
            "triggerCount": 0,
            "tags": [],
        }

    # Legacy stub variant: both "id" (name) and "workflowId" (internal id) present.
    if isinstance(src, dict) and "workflowId" in src and "nodes" in src and "connections" in src:
        name = src.get("name") or src.get("id") or "Unnamed workflow"
        settings = src.get("settings") or {}
        meta = src.get("meta") or {}
        return {
            "name": name,
            "nodes": src.get("nodes") or [],
            "connections": src.get("connections") or {},
            "settings": settings,
            "staticData": src.get("staticData"),
            # Import stub flows as inactive; activation is a separate step.
            "active": False,
            "meta": meta,
            "pinData": None,
            "versionId": str(uuid.uuid4()),
            "versionCounter": 1,
            "triggerCount": 0,
            "tags": [],
        }

    # Full export (CLI): already has name/nodes/connections; strip user/project metadata.
    if isinstance(src, dict) and "name" in src and "nodes" in src and "connections" in src:
        return {
            "name": src.get("name") or "Unnamed workflow",
            "nodes": src.get("nodes") or [],
            "connections": src.get("connections") or {},
            "settings": src.get("settings") or {},
            "staticData": src.get("staticData"),
            # Keep repo exports importable across fresh instances: import inactive, then activate explicitly.
            "active": False,
            "meta": src.get("meta") or {},
            "pinData": src.get("pinData"),
            "versionId": src.get("versionId") or str(uuid.uuid4()),
            "versionCounter": int(src.get("versionCounter") or 1),
            "triggerCount": int(src.get("triggerCount") or 0),
            "tags": src.get("tags") or [],
        }

    raise ValueError(f"Unrecognized workflow JSON shape. Keys: {sorted(src.keys()) if isinstance(src, dict) else type(src)}")


def normalize_file(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = [_as_workflow_obj(data)]
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Normalize n8n workflow JSON into an importable minimal format.")
    ap.add_argument("--inplace-dir", type=Path, help="Directory to normalize in place (all *.json files)")
    ap.add_argument("--file", type=Path, help="Single JSON file to normalize in place")
    args = ap.parse_args()

    if bool(args.inplace_dir) == bool(args.file):
        ap.error("Provide exactly one of --inplace-dir or --file")

    if args.file:
        normalize_file(args.file)
        return 0

    directory: Path = args.inplace_dir
    for f in sorted(directory.glob("*.json")):
        normalize_file(f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
