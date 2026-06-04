#!/usr/bin/env python3
"""CHIT secrets-manifest merge-conflict resolver.

Resolves a git merge conflict in ``pmoves/chit/secrets_manifest*.yaml`` by
**unioning the ``entries`` list by ``id``**. This is the correct resolution for
the common *additive* conflict where two branches each appended different secret
entries (e.g. `main` added WGER_* while a feature branch added MEILI_*). Taking
one side wholesale (`git checkout --ours/--theirs`) would silently DROP the other
side's secrets — this tool keeps both.

Why this lives here (and not raw git): the manifest is a ``zeroAccessPaths``
file in the damage-control guard. This tool is registered in
``chitBypassPatterns`` so it — and only it — may read/write the manifest for
conflict resolution. It is deliberately conservative:

  * It REFUSES to auto-resolve a true content collision (same ``id`` on both
    sides with different bodies) — those are reported for a human decision.
  * It REFUSES if the top-level (``version`` / ``cgp_file`` / ``defaults``)
    diverges between the two sides — that is a structural change, not an
    additive entry conflict, and must be resolved deliberately.
  * ``--check`` reports what it would do and writes nothing.

Usage:
  python pmoves/tools/chit_manifest_merge.py pmoves/chit/secrets_manifest_v2.yaml
  python pmoves/tools/chit_manifest_merge.py --check pmoves/chit/secrets_manifest_v2.yaml

Exit codes:
  0  resolved cleanly (or --check found a clean additive union)
  2  collision / structural divergence — human resolution required
  3  no conflict markers found / not a conflicted file
  4  parse or usage error
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

CONFLICT_START = "<<<<<<<"
CONFLICT_SEP = "======="
CONFLICT_END = ">>>>>>>"


def split_sides(text: str) -> Tuple[str, str, int]:
    """Reconstruct the 'ours' and 'theirs' full documents from a conflicted file.

    Returns (ours_text, theirs_text, hunk_count). Common (non-conflicted) lines
    go to both sides; conflict hunks contribute their HEAD section to ours and
    their incoming section to theirs.
    """
    ours: List[str] = []
    theirs: List[str] = []
    state = "common"  # common | ours | theirs
    hunks = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\n").rstrip("\r")
        if stripped.startswith(CONFLICT_START):
            state = "ours"
            hunks += 1
            continue
        if stripped == CONFLICT_SEP and state == "ours":
            state = "theirs"
            continue
        if stripped.startswith(CONFLICT_END):
            state = "common"
            continue
        if state == "common":
            ours.append(line)
            theirs.append(line)
        elif state == "ours":
            ours.append(line)
        else:  # theirs
            theirs.append(line)
    return "".join(ours), "".join(theirs), hunks


def _entries_by_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    entries = doc.get("entries")
    if not isinstance(entries, list):
        raise ValueError("manifest 'entries' is not a list")
    out: Dict[str, Any] = {}
    for item in entries:
        if not isinstance(item, dict) or "id" not in item:
            raise ValueError(f"manifest entry missing 'id': {item!r}")
        eid = item["id"]
        if eid in out:
            raise ValueError(f"duplicate id within one side: {eid}")
        out[eid] = item
    return out


def _top_level_signature(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Everything except the entries list — must match across both sides."""
    return {k: v for k, v in doc.items() if k != "entries"}


def resolve(text: str) -> Tuple[str, List[str]]:
    """Return (merged_yaml_text, notes). Raises SystemExit(2/3/4) on failure."""
    if CONFLICT_START not in text:
        print("No conflict markers found — nothing to resolve.", file=sys.stderr)
        raise SystemExit(3)

    ours_text, theirs_text, hunks = split_sides(text)
    try:
        ours = yaml.safe_load(ours_text)
        theirs = yaml.safe_load(theirs_text)
    except yaml.YAMLError as e:
        print(f"Failed to parse a conflict side as YAML: {e}", file=sys.stderr)
        raise SystemExit(4)

    if not isinstance(ours, dict) or not isinstance(theirs, dict):
        print("Manifest sides did not parse to mappings.", file=sys.stderr)
        raise SystemExit(4)

    sig_ours = _top_level_signature(ours)
    sig_theirs = _top_level_signature(theirs)
    if sig_ours != sig_theirs:
        diff_keys = sorted(
            k for k in set(sig_ours) | set(sig_theirs)
            if sig_ours.get(k) != sig_theirs.get(k)
        )
        print(
            "STRUCTURAL DIVERGENCE — top-level differs between sides on: "
            f"{', '.join(diff_keys)}.\nThis is not an additive entry conflict; "
            "resolve deliberately (human).",
            file=sys.stderr,
        )
        raise SystemExit(2)

    ours_entries = _entries_by_id(ours)
    theirs_entries = _entries_by_id(theirs)

    collisions: List[str] = []
    for eid in sorted(set(ours_entries) & set(theirs_entries)):
        if ours_entries[eid] != theirs_entries[eid]:
            collisions.append(eid)
    if collisions:
        print(
            "CONTENT COLLISION — these ids exist on BOTH sides with different "
            f"bodies and cannot be auto-unioned: {', '.join(collisions)}.\n"
            "A human must reconcile these entries.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    # Clean additive union: preserve ours' order, then append theirs-only ids.
    merged_entries: List[Any] = list(ours.get("entries", []))
    ours_ids = set(ours_entries)
    added: List[str] = []
    for eid in theirs_entries:
        if eid not in ours_ids:
            merged_entries.append(theirs_entries[eid])
            added.append(eid)

    merged = dict(ours)  # preserves top-level key order from ours
    merged["entries"] = merged_entries

    notes = [
        f"hunks={hunks}",
        f"ours_entries={len(ours_entries)}",
        f"theirs_entries={len(theirs_entries)}",
        f"added_from_theirs={len(added)} ({', '.join(added) if added else 'none'})",
        f"total={len(merged_entries)}",
    ]
    merged_text = yaml.safe_dump(merged, sort_keys=False, default_flow_style=False, width=4096)
    return merged_text, notes


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Union-merge a conflicted CHIT secrets manifest by id.")
    ap.add_argument("manifest", help="path to the conflicted secrets_manifest*.yaml")
    ap.add_argument("--check", action="store_true", help="report only; do not write")
    args = ap.parse_args(argv)

    path = Path(args.manifest)
    if "secrets_manifest" not in path.name:
        print(f"Refusing: {path.name} is not a secrets_manifest file.", file=sys.stderr)
        return 4
    if not path.exists():
        print(f"Not found: {path}", file=sys.stderr)
        return 4

    text = path.read_text(encoding="utf-8")
    merged_text, notes = resolve(text)

    print("CHIT manifest merge — clean additive union:")
    for n in notes:
        print(f"  {n}")

    if args.check:
        print("--check: no file written.")
        return 0

    path.write_text(merged_text, encoding="utf-8", newline="\n")
    print(f"Wrote resolved manifest: {path}")
    print("Next: validate with `make -C pmoves manifest-audit`, then `git add` the manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
