#!/usr/bin/env python3
"""Verify .gitmodules branch policy for production release gating."""

from __future__ import annotations

import argparse
import configparser
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GITMODULES = REPO_ROOT / ".gitmodules"


@dataclass
class BranchRow:
    name: str
    path: str
    branch: str


def parse_gitmodules(path: Path) -> list[BranchRow]:
    parser = configparser.RawConfigParser()
    parser.read(path, encoding="utf-8")
    rows: list[BranchRow] = []
    for section in parser.sections():
        if not section.startswith("submodule "):
            continue
        name = section.split('"', 2)[1] if '"' in section else section
        rows.append(
            BranchRow(
                name=name,
                path=parser.get(section, "path", fallback=""),
                branch=parser.get(section, "branch", fallback=""),
            )
        )
    return rows


def _expand_entries(values: list[str]) -> list[str]:
    """Expand comma-packed entries like 'A=b,C=d' into ['A=b', 'C=d'].

    Commas that appear *before* the first '=' in a token are name
    separators (e.g. 'A,B=branch'), not entry delimiters.  Only commas
    that are followed by a new 'name=branch' pair split entries.
    """
    entries: list[str] = []
    for raw in values:
        # Split on commas that precede a new NAME=BRANCH pair.
        # We detect this by re-joining fragments that lack '='.
        buf = ""
        for fragment in raw.split(","):
            if "=" in fragment and buf:
                entries.append(buf.strip())
                buf = fragment
            elif buf:
                buf += "," + fragment
            else:
                buf = fragment
        if buf.strip():
            entries.append(buf.strip())
    return entries


def parse_allow(values: list[str]) -> dict[str, set[str]]:
    allowed: dict[str, set[str]] = {}
    for text in _expand_entries(values):
        if not text or "=" not in text:
            continue
        key, rhs = text.split("=", 1)
        names = [part.strip() for part in key.split(",") if part.strip()]
        branches = {part.strip() for part in rhs.split(",") if part.strip()}
        if not names or not branches:
            continue
        for name in names:
            allowed.setdefault(name, set()).update(branches)
    return allowed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--default",
        default="PMOVES.AI-Edition-Hardened",
        help="Default required branch for submodules.",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        help="Optional override(s) in `submodule=branch1,branch2` form (repeatable).",
    )
    args = parser.parse_args()

    if not GITMODULES.exists():
        print(f"FAIL: missing {GITMODULES}")
        return 2

    rows = parse_gitmodules(GITMODULES)
    allowed = parse_allow(args.allow)

    failures: list[str] = []
    missing: list[str] = []
    for row in rows:
        if not row.branch:
            missing.append(f"{row.name} ({row.path})")
            continue
        accepted = {args.default}
        accepted.update(allowed.get(row.name, set()))
        accepted.update(allowed.get(row.path, set()))
        if row.branch not in accepted:
            failures.append(
                f"{row.name} ({row.path}) -> {row.branch} (expected one of: {', '.join(sorted(accepted))})"
            )

    if missing or failures:
        print("FAIL: submodule branch policy check failed")
        if missing:
            print("Missing branch field:")
            for item in missing:
                print(f"  - {item}")
        if failures:
            print("Branch policy mismatches:")
            for item in failures:
                print(f"  - {item}")
        return 1

    print("PASS: submodule branch policy check passed")
    print(f"  - checked: {len(rows)}")
    print(f"  - default branch: {args.default}")
    if allowed:
        print("  - overrides:")
        for key in sorted(allowed):
            print(f"    - {key}: {', '.join(sorted(allowed[key]))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

