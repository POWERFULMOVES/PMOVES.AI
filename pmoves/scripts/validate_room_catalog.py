#!/usr/bin/env python3
"""Assert every catalog row's `current_stage` was earned, not seeded.

WHY THIS EXISTS
---------------
`pmoves/config/rooms/catalog.json` carries a `current_stage` per room row.
It is not decoration: `p7-room-orchestrator/catalog.py::current_stage` reads
it, and `transition.py` branches on it --

    current = self._catalog.current_stage(room_id)
    if current == target_stage:
        return {... "noop": True}          # returns BEFORE the CHIT gate
    ...
    if current == "rehearsal" and target_stage == "live":
        unchecked = self.check_chit_activation(manifest)   # 7-item checklist

So a row that already says "live" makes `rehearsal -> live` a no-op and the
CHIT activation checklist (signing card, identity-card row, sign-trail)
unreachable for that room. A wrong value here does not fail loudly; it
silently removes a gate.

Three rows shipped that way. The Open Room lane CLAIM (AGNOTE4482PHI.t1.md,
2026-07-20) specified the source exactly:

    "(2) add `current_stage` field to `catalog.json` room rows
     (read from each manifest's `stage` field)"

The RELEASE the same day reported "3 live / 5 rehearsal / 1 archive" against
manifests that read 1 live / 12 rehearsal, with `stage_source` recorded as
"ROOMS_ON_A_STAGE.md typical-stage table" -- a documentation table of typical
stages, substituted for the manifests. Nobody read the release back against
the claim, so the divergence sat for 50 days. This check is that read-back,
made mechanical.

THE RULE
--------
A row's `current_stage` is trustworthy only if one of these holds:

  (a) P7 wrote it. `catalog.py::update_stage` stamps
      `stage_source = "P7 transition (catalog writeback)"` on every
      transition it performs, so that exact string is an activation receipt.
  (b) It agrees with the room manifest's own `stage`.

Anything else is a value that outranks the manifest with no activation
behind it. Prose may explain a stage; it may not confer one.

A third source was considered and deliberately not added: the catalog's
`_version_notes` used to name "each manifest's `p7.stage` block (if present)"
alongside the typical-stage table. Measured 2026-09-08 -- a `p7` block exists
in exactly two files, `demo.room.extras.json` and
`hermes-agent.room.control.extras.json`, both reading `rehearsal` in agreement
with their rooms' manifests, and no catalog row's `manifest` field points at an
`.extras.json`. So honouring `p7.stage` would change no verdict today while
adding a second place a stage could come from. Rule (b) already covers both.

Exit codes: 0 = every row accounted for, 2 = at least one seeded row.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO / "config" / "rooms" / "catalog.json"
ROOMS_DIR = REPO / "config" / "rooms"

# The exact string p7-room-orchestrator/catalog.py::update_stage stamps.
# Keep byte-identical with that writer; see the module docstring.
P7_WRITEBACK_SOURCE = "P7 transition (catalog writeback)"


def manifest_stage(manifest_name: str) -> str | None:
    """Return the `stage` a room manifest declares, or None if unreadable."""
    path = ROOMS_DIR / manifest_name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("stage")
    except (json.JSONDecodeError, OSError):
        return None


def main() -> int:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    rows = catalog.get("rooms", [])

    seeded: list[str] = []
    checked = 0

    for row in rows:
        room_id = row.get("room_id", "(no room_id)")
        current = row.get("current_stage")
        if current is None:
            # Rows predating catalog schema 1.2.0 carry no current_stage.
            # P7 treats that as "no stage on file" and the state machine
            # rejects every target, which is a refusal, not a bypass.
            continue

        checked += 1
        source = row.get("stage_source", "")

        if source == P7_WRITEBACK_SOURCE:
            print(f"OK       {room_id}: current_stage={current} (P7 activation receipt)")
            continue

        declared = manifest_stage(row.get("manifest", ""))
        if declared is None:
            seeded.append(
                f"{room_id}: manifest {row.get('manifest')!r} is missing or unreadable, "
                f"so current_stage={current!r} cannot be checked against anything"
            )
            print(f"SEEDED   {room_id}: manifest unreadable")
            continue

        if current == declared:
            print(f"OK       {room_id}: current_stage={current} == manifest stage")
            continue

        seeded.append(
            f"{room_id}: current_stage={current!r} but the manifest declares "
            f"stage={declared!r}, and stage_source is {source!r} -- not a P7 "
            f"activation. P7 will treat a rehearsal->{current} request as a "
            f"no-op and never run check_chit_activation for this room."
        )
        print(f"SEEDED   {room_id}: current_stage={current} != manifest stage={declared}")

    print()
    print(f"room-catalog-stage: {len(rows)} rows, {checked} with current_stage, {len(seeded)} seeded")

    if seeded:
        print()
        print("A seeded stage removes a gate silently. Either transition the room")
        print("through P7 (which writes the receipt), or set current_stage to the")
        print("stage its manifest actually declares:")
        for problem in seeded:
            print(f"  - {problem}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
