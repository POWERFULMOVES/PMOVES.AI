#!/usr/bin/env python3
"""Trigger the CHIT+OAuth-gated showtime updater from the CLI / make target.

Loads the self-contained updater logic from
``pmoves/services/showtime-api/updater.py`` (a non-package directory, so we
import by file path), evaluates the two-factor gate, and — when unlocked —
runs a blast-radius-scoped update against the SAFE DEFAULT (data-tier) radius.

Exit codes:
    0  update ran (or dry-run) successfully
    1  gate locked / update aborted (dirty worktree, forbidden radius, ...)
    2  internal error (could not load updater module)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

PMOVES_ROOT = Path(__file__).resolve().parents[1]
UPDATER_PATH = PMOVES_ROOT / "services" / "showtime-api" / "updater.py"


def _load_updater() -> ModuleType:
    spec = importlib.util.spec_from_file_location("showtime_updater", UPDATER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load updater module from {UPDATER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-chit",
        action="store_true",
        help="Escape hatch for headless CI: bypass the CHIT factor only "
        "(also settable via SHOWTIME_UPDATER_SKIP_CHIT=1).",
    )
    parser.add_argument(
        "--blast-radius",
        default="",
        help="Comma-separated service allowlist. Default: SAFE DEFAULT (data-tier).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not pull images.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    try:
        updater = _load_updater()
    except ImportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    gate = updater.evaluate_gate(skip_chit=args.skip_chit)
    if not gate.get("unlocked"):
        if args.json:
            print(json.dumps({"gate": gate, "update": None}, indent=2))
        else:
            print(f"GATE LOCKED: {gate.get('reason')}")
            print("  hint: set CHIT_PASSPHRASE + a Google session token, "
                  "or pass --skip-chit for headless CI.")
        return 1

    radius = [s.strip() for s in args.blast_radius.split(",") if s.strip()] or None
    summary = updater.run_update(radius, dry_run=args.dry_run)

    if args.json:
        print(json.dumps({"gate": gate, "update": summary}, indent=2))
    else:
        print(f"GATE: {gate.get('reason')}")
        print(f"UPDATE [{summary.get('status')}]: {summary.get('reason')}")
        print(f"  blast_radius: {summary.get('blast_radius')}")
        for entry in summary.get("acted_on", []):
            print(f"  acted: {entry}")
        if summary.get("skipped"):
            print(f"  skipped (not updatable): {summary.get('skipped')}")

    return 0 if summary.get("status") in {"ok", "noop"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
